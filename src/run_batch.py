"""
Batch runner — integrates all 6 upgrade features:

  F1: Razorpay test-mode API calls on recovered/escalated outcomes
  F2: A/B comparison (rule-based vs ML stopping) → ab_comparison.json
  F3: Cost/ROI calculation → embedded in batch_summary.json
  F4: Structured explainability dict per decision
  F5: Multi-direction support (payment / checkout / subscription / B2B)
  F6: Output consumed by SSE simulation endpoint in app/routers/batch.py

Pipeline (same shape as before, extended output):
  for each transaction:
    1. get_root_cause()  [rules engine — F5 extended]
    2. get_action()      [rules engine]
    3. get_direction()   [rules engine — F5]
    4. ML predict_proba  [stopping model]
    5. stopping decision [ML threshold + hard cap]
    6. razorpay_client   [F1 — capture or refund]
    7. explainability    [F4 — structured dict]
    8. generate_message  [LLM / fallback]
  produce audit log → batch_summary (with ROI) → ab_comparison
"""

import pandas as pd
import joblib
import json
import os
from datetime import datetime

from src.rules_engine import get_root_cause, get_action, get_direction
from src.messaging import generate_message
from src.razorpay_client import RazorpayClient
from src.ab_comparison import compare_batch
from src.roi_calculator import compute_roi

STOPPING_THRESHOLD = 0.20
MAX_ATTEMPTS = 3


# ── Helpers ────────────────────────────────────────────────────────────────


def load_pipeline_components():
    model = joblib.load("models/stopping_model.pkl")
    df = pd.read_csv("data/failed_transactions.csv")
    return model, df


def _decision_path(row, recovery_probability: float, final_status: str) -> list[str]:
    """Returns the ordered list of rule checks that led to this decision."""
    path = ["start"]
    if row["attempt_number"] >= MAX_ATTEMPTS:
        path.append("attempt_cap_reached")
    else:
        path.append("attempt_cap_ok")
        if recovery_probability < STOPPING_THRESHOLD:
            path.append("ml_probability_below_threshold")
        else:
            path.append("ml_probability_above_threshold")
    path.append(final_status)
    return path


def _confidence_label(recovery_probability: float, final_status: str) -> str:
    """Simple confidence tier for the explainability layer."""
    if final_status == "escalated_max_attempts":
        return "rule_triggered"   # deterministic, not probability-based
    if abs(recovery_probability - STOPPING_THRESHOLD) > 0.25:
        return "high"             # well away from decision boundary
    if abs(recovery_probability - STOPPING_THRESHOLD) > 0.10:
        return "medium"
    return "low"                  # near the boundary — borderline call


def build_explainability(
    row, root_cause: str, recovery_probability: float, final_status: str
) -> dict:
    """
    Feature 4: Structured explainability dict.

    Replaces the flat 'reasoning' string with a machine-readable object
    that includes the decision path, factors, confidence, and a
    human-readable summary — useful for compliance audit and the
    "Explain Decision" modal in the dashboard.
    """
    if final_status == "escalated_max_attempts":
        summary = (
            f"Escalated because attempt_number={row['attempt_number']} "
            f"reached the hard cap of {MAX_ATTEMPTS} retries regardless of "
            f"predicted recovery probability ({recovery_probability:.1%})."
        )
    elif final_status == "escalated_low_probability":
        summary = (
            f"Escalated on attempt {row['attempt_number']} — predicted "
            f"recovery probability ({recovery_probability:.1%}) was below "
            f"the {STOPPING_THRESHOLD:.0%} threshold, so retrying was "
            f"judged not worth the cost/risk."
        )
    elif final_status == "recovered":
        summary = (
            f"Retried based on root_cause='{root_cause}' "
            f"(predicted {recovery_probability:.1%} above threshold) "
            f"— retry succeeded."
        )
    else:
        summary = (
            f"Retried based on root_cause='{root_cause}' "
            f"(predicted {recovery_probability:.1%} above threshold) "
            f"— retry attempted but did not succeed."
        )

    return {
        "decision_path": _decision_path(row, recovery_probability, final_status),
        "factors": {
            "attempt_number": int(row["attempt_number"]),
            "max_attempts_cap": MAX_ATTEMPTS,
            "recovery_probability": round(recovery_probability, 4),
            "stopping_threshold": STOPPING_THRESHOLD,
            "stopping_rule_triggered": (
                "max_attempts" if row["attempt_number"] >= MAX_ATTEMPTS
                else "ml_below_threshold" if recovery_probability < STOPPING_THRESHOLD
                else "none"
            ),
            "root_cause": root_cause,
            "direction": get_direction(row["failure_code"]),
        },
        "confidence": _confidence_label(recovery_probability, final_status),
        "human_readable": summary,
    }


# ── Core pipeline ──────────────────────────────────────────────────────────


def process_transaction(row, model, razorpay_client: RazorpayClient) -> dict:
    """
    Runs one transaction through the full pipeline. Returns a dict
    representing one audit log entry (superset of the original schema).
    """
    root_cause = get_root_cause(row["failure_code"])
    action = get_action(root_cause)
    direction = get_direction(row["failure_code"])

    # ML stopping decision
    input_df = pd.DataFrame([{
        "payment_method": row["payment_method"],
        "root_cause": root_cause,
        "amount": row["amount"],
        "attempt_number": row["attempt_number"],
    }])
    recovery_probability = model.predict_proba(input_df)[0][1]

    # Stopping decision
    if row["attempt_number"] >= MAX_ATTEMPTS:
        final_status = "escalated_max_attempts"
    elif recovery_probability < STOPPING_THRESHOLD:
        final_status = "escalated_low_probability"
    else:
        final_status = "recovered" if row.get("recovered", 0) == 1 else "retry_failed"

    # Feature 1: Razorpay API call
    razorpay_response = None
    if final_status == "recovered":
        razorpay_response = razorpay_client.capture_payment(
            payment_id=row["transaction_id"],
            amount=row["amount"],
        )
    elif final_status.startswith("escalated"):
        razorpay_response = razorpay_client.create_refund(
            payment_id=row["transaction_id"],
            amount=row["amount"],
        )

    # Feature 4: Structured explainability
    explainability = build_explainability(row, root_cause, recovery_probability, final_status)

    # LLM customer message
    message = generate_message(root_cause, action)

    return {
        "transaction_id":       row["transaction_id"],
        "customer_id":          row["customer_id"],
        "amount":               row["amount"],
        "payment_method":       row["payment_method"],
        "failure_code":         row["failure_code"],
        "direction":            direction,
        "root_cause":           root_cause,
        "recommended_action":   action,
        "recovery_probability": round(recovery_probability, 3),
        "attempt_number":       row["attempt_number"],
        "final_status":         final_status,
        # F4 — structured (stored as JSON string in CSV for compatibility)
        "explainability":       json.dumps(explainability),
        # Keep flat reasoning for backward-compat readers
        "reasoning":            explainability["human_readable"],
        "customer_message":     message,
        # F1 — Razorpay response (None for retry_failed which doesn't call API)
        "razorpay_response":    json.dumps(razorpay_response) if razorpay_response else None,
        "razorpay_mode":        razorpay_client.mode,
        "processed_at":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        # Keep raw recovered label for A/B comparison module
        "recovered":            row.get("recovered", 0),
    }


# ── Batch orchestration ────────────────────────────────────────────────────


def run_batch():
    print("Loading model and dataset...")
    model, df = load_pipeline_components()
    razorpay_client = RazorpayClient()
    print(f"Razorpay mode: {razorpay_client.mode} (live sample limit: {razorpay_client._live_calls})")
    print(f"Processing {len(df)} transactions across {df['direction'].nunique() if 'direction' in df.columns else 1} direction(s)...\n")

    audit_log = []
    for _, row in df.iterrows():
        entry = process_transaction(row, model, razorpay_client)
        audit_log.append(entry)

    audit_df = pd.DataFrame(audit_log)

    os.makedirs("data", exist_ok=True)
    audit_df.to_csv("data/audit_log.csv", index=False)
    print(f"Audit log saved -> data/audit_log.csv ({len(audit_df)} rows)")

    # Feature 2: A/B comparison
    print("Running A/B comparison (rule-based vs ML)...")
    ab_result = compare_batch(audit_df)
    with open("data/ab_comparison.json", "w") as f:
        json.dump(ab_result, f, indent=2)
    print("A/B comparison saved -> data/ab_comparison.json")

    # Feature 3: ROI calculation (embedded in summary)
    roi_result = compute_roi(audit_df)

    summary = build_summary(audit_df, razorpay_client.mode, ab_result, roi_result)

    with open("data/batch_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("Batch summary saved -> data/batch_summary.json")

    print_summary(summary)
    return audit_df, summary


def build_summary(
    audit_df: pd.DataFrame,
    razorpay_mode: str,
    ab_result: dict,
    roi_result: dict,
) -> dict:
    total_transactions = len(audit_df)
    total_amount_at_risk = round(audit_df["amount"].sum(), 2)

    recovered          = audit_df[audit_df["final_status"] == "recovered"]
    escalated_max      = audit_df[audit_df["final_status"] == "escalated_max_attempts"]
    escalated_low_prob = audit_df[audit_df["final_status"] == "escalated_low_probability"]
    retry_failed       = audit_df[audit_df["final_status"] == "retry_failed"]

    total_recovered_amount = round(recovered["amount"].sum(), 2)
    recovery_rate = (
        round(len(recovered) / total_transactions * 100, 1)
        if total_transactions else 0
    )

    # Per-direction breakdown (Feature 5)
    per_direction = {}
    if "direction" in audit_df.columns:
        for direction, grp in audit_df.groupby("direction"):
            dir_recovered = grp[grp["final_status"] == "recovered"]
            per_direction[direction] = {
                "total": len(grp),
                "recovered_count": len(dir_recovered),
                "recovered_amount": round(dir_recovered["amount"].sum(), 2),
                "recovery_rate_percent": round(
                    len(dir_recovered) / len(grp) * 100, 1
                ) if len(grp) else 0,
            }

    return {
        "total_transactions":   total_transactions,
        "total_amount_at_risk": total_amount_at_risk,
        "razorpay_mode":        razorpay_mode,
        "recovered": {
            "count":  len(recovered),
            "amount": total_recovered_amount,
        },
        "escalated_max_attempts": {
            "count":  len(escalated_max),
            "amount": round(escalated_max["amount"].sum(), 2),
        },
        "escalated_low_probability": {
            "count":  len(escalated_low_prob),
            "amount": round(escalated_low_prob["amount"].sum(), 2),
        },
        "retry_failed": {
            "count":  len(retry_failed),
            "amount": round(retry_failed["amount"].sum(), 2),
        },
        "recovery_rate_percent":  recovery_rate,
        "root_cause_breakdown":   audit_df["root_cause"].value_counts().to_dict(),
        "per_direction":          per_direction,
        "ab_comparison_summary": {
            "rule_recovery_rate":   ab_result["rule_based"]["recovery_rate_percent"],
            "ml_recovery_rate":     ab_result["ml_augmented"]["recovery_rate_percent"],
            "rate_delta_pp":        ab_result["ml_advantage"]["recovery_rate_delta_pp"],
            "cost_savings_inr":     ab_result["ml_advantage"]["operational_cost_savings"],
            "net_value_uplift_inr": ab_result["ml_advantage"]["net_value_uplift"],
        },
        "roi": roi_result,
    }


def print_summary(summary: dict):
    print("\n" + "=" * 55)
    print("BATCH SUMMARY")
    print("=" * 55)
    print(f"Razorpay mode             : {summary['razorpay_mode'].upper()}")
    print(f"Total transactions        : {summary['total_transactions']}")
    print(f"Total amount at risk      : INR {summary['total_amount_at_risk']:,.2f}")
    print(f"\nRecovered                 : {summary['recovered']['count']} txns, INR {summary['recovered']['amount']:,.2f}")
    print(f"Escalated (max attempts)  : {summary['escalated_max_attempts']['count']} txns")
    print(f"Escalated (low prob)      : {summary['escalated_low_probability']['count']} txns")
    print(f"Retry failed              : {summary['retry_failed']['count']} txns")
    print(f"\nRecovery rate             : {summary['recovery_rate_percent']}%")
    ab = summary["ab_comparison_summary"]
    print(f"\nA/B uplift (ML vs rules)  : {ab['rate_delta_pp']:+.1f} pp recovery rate")
    print(f"Operational cost savings  : INR {ab['cost_savings_inr']:,.2f}")
    roi = summary["roi"]["roi"]
    print(f"\nNet ROI                   : INR {roi['net_roi']:,.2f} ({roi['cost_efficiency_percent']}%)")
    print("=" * 55)


if __name__ == "__main__":
    run_batch()

    