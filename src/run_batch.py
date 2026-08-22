"""
Phase 5: Batch runner + audit log.

Combines rules_engine (root cause + action), train_model (ML stopping
decision), and messaging (customer notification) into one pipeline.
Runs it across the full synthetic dataset, logs every decision, and
produces a batch-level summary report — the core numbers for the pitch.
"""

import pandas as pd
import joblib
import json
import os
from datetime import datetime

from src.rules_engine import get_root_cause, get_action
from src.messaging import generate_message

# Below this recovery-probability threshold, we stop retrying and
# escalate immediately instead — avoids wasting retries on transactions
# unlikely to recover.
STOPPING_THRESHOLD = 0.20

# Hard cap regardless of ML prediction — never retry more than this many
# times, even if the model is optimistic. This is the "compliant
# escalation" safety net required by the track.
MAX_ATTEMPTS = 3


def load_pipeline_components():
    model = joblib.load("models/stopping_model.pkl")
    df = pd.read_csv("data/failed_transactions.csv")
    return model, df


def process_transaction(row, model):
    """Runs one transaction through the full pipeline: root cause,
    action, ML stopping decision, and message generation. Returns a
    dict representing one audit log entry."""

    root_cause = get_root_cause(row["failure_code"])
    action = get_action(root_cause)

    # predict recovery probability using the trained model
    input_df = pd.DataFrame([{
        "payment_method": row["payment_method"],
        "root_cause": root_cause,
        "amount": row["amount"],
        "attempt_number": row["attempt_number"],
    }])
    recovery_probability = model.predict_proba(input_df)[0][1]

    # stopping decision: hard cap on attempts OR low predicted probability
    if row["attempt_number"] >= MAX_ATTEMPTS:
        final_status = "escalated_max_attempts"
    elif recovery_probability < STOPPING_THRESHOLD:
        final_status = "escalated_low_probability"
    else:
        # simulate the actual outcome using our synthetic ground-truth
        # label (in a real system, this would be the real retry result)
        final_status = "recovered" if row["recovered"] == 1 else "retry_failed"

    message = generate_message(root_cause, action)

    return {
        "transaction_id": row["transaction_id"],
        "customer_id": row["customer_id"],
        "amount": row["amount"],
        "payment_method": row["payment_method"],
        "failure_code": row["failure_code"],
        "root_cause": root_cause,
        "recommended_action": action,
        "recovery_probability": round(recovery_probability, 3),
        "attempt_number": row["attempt_number"],
        "final_status": final_status,
        "customer_message": message,
        "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def run_batch():
    print("Loading model and dataset...")
    model, df = load_pipeline_components()
    print(f"Processing {len(df)} transactions...\n")

    audit_log = []
    for _, row in df.iterrows():
        entry = process_transaction(row, model)
        audit_log.append(entry)

    audit_df = pd.DataFrame(audit_log)

    os.makedirs("data", exist_ok=True)
    audit_df.to_csv("data/audit_log.csv", index=False)
    print(f"Audit log saved -> data/audit_log.csv ({len(audit_df)} rows)")

    summary = build_summary(audit_df)

    with open("data/batch_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("Batch summary saved -> data/batch_summary.json")

    print_summary(summary)
    return audit_df, summary


def build_summary(audit_df: pd.DataFrame) -> dict:
    total_transactions = len(audit_df)
    total_amount_at_risk = round(audit_df["amount"].sum(), 2)

    recovered = audit_df[audit_df["final_status"] == "recovered"]
    escalated_max = audit_df[audit_df["final_status"] == "escalated_max_attempts"]
    escalated_low_prob = audit_df[audit_df["final_status"] == "escalated_low_probability"]
    retry_failed = audit_df[audit_df["final_status"] == "retry_failed"]

    total_recovered_amount = round(recovered["amount"].sum(), 2)
    recovery_rate = round(len(recovered) / total_transactions * 100, 1) if total_transactions else 0

    return {
        "total_transactions": total_transactions,
        "total_amount_at_risk": total_amount_at_risk,
        "recovered": {
            "count": len(recovered),
            "amount": total_recovered_amount,
        },
        "escalated_max_attempts": {
            "count": len(escalated_max),
            "amount": round(escalated_max["amount"].sum(), 2),
        },
        "escalated_low_probability": {
            "count": len(escalated_low_prob),
            "amount": round(escalated_low_prob["amount"].sum(), 2),
        },
        "retry_failed": {
            "count": len(retry_failed),
            "amount": round(retry_failed["amount"].sum(), 2),
        },
        "recovery_rate_percent": recovery_rate,
        "root_cause_breakdown": audit_df["root_cause"].value_counts().to_dict(),
    }


def print_summary(summary: dict):
    print("\n" + "=" * 50)
    print("BATCH SUMMARY")
    print("=" * 50)
    print(f"Total transactions processed : {summary['total_transactions']}")
    print(f"Total amount at risk         : ₹{summary['total_amount_at_risk']:,.2f}")
    print(f"\nRecovered                    : {summary['recovered']['count']} txns, ₹{summary['recovered']['amount']:,.2f}")
    print(f"Escalated (max attempts)     : {summary['escalated_max_attempts']['count']} txns, ₹{summary['escalated_max_attempts']['amount']:,.2f}")
    print(f"Escalated (low probability)  : {summary['escalated_low_probability']['count']} txns, ₹{summary['escalated_low_probability']['amount']:,.2f}")
    print(f"Retry attempted but failed   : {summary['retry_failed']['count']} txns, ₹{summary['retry_failed']['amount']:,.2f}")
    print(f"\nRecovery rate                : {summary['recovery_rate_percent']}%")
    print("=" * 50)


if __name__ == "__main__":
    run_batch()