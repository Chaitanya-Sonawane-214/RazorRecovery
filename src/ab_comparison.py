"""
Feature 2: A/B Comparison — Rule-Based vs ML Stopping.

Runs both decision strategies on every transaction and computes the
quantified difference. This is the "business case proof" for why ML
stopping is worth it over a naive retry-N-times rule.

Rule-based baseline:
  - Stop if attempt_number >= MAX_ATTEMPTS (hard cap only)
  - Otherwise always retry

ML strategy (existing system):
  - Stop if attempt_number >= MAX_ATTEMPTS (same hard cap)
  - Also stop if recovery_probability < STOPPING_THRESHOLD
  - Otherwise retry

The delta between the two shows:
  - How many unnecessary retries ML avoids
  - How much that saves in retry cost
  - Whether ML catches more recoveries or fewer (tradeoff)
"""

import pandas as pd

# Must match the values in run_batch.py — these are the live thresholds
MAX_ATTEMPTS = 3
STOPPING_THRESHOLD = 0.20

# Cost assumptions (INR) — realistic estimates for SMS + gateway overhead
RETRY_COST_PER_ATTEMPT = 0.50   # cost of one retry attempt
ESCALATION_COST_HUMAN = 5.00    # cost of human-review escalation


def rule_based_decision(row: dict) -> str:
    """
    Pure rule-based stopping decision (the baseline / 'control' arm).
    Only uses the hard attempt cap — no ML probability involved.
    Returns a final_status string matching the pipeline's vocabulary.
    """
    if row["attempt_number"] >= MAX_ATTEMPTS:
        return "escalated_max_attempts"
    # Rules say: always retry if under cap
    return "recovered" if row.get("recovered", 0) == 1 else "retry_failed"


def ml_decision(row: dict, recovery_probability: float) -> str:
    """
    ML-augmented stopping decision (the 'treatment' arm).
    Mirrors the logic in run_batch.process_transaction() exactly.
    """
    if row["attempt_number"] >= MAX_ATTEMPTS:
        return "escalated_max_attempts"
    if recovery_probability < STOPPING_THRESHOLD:
        return "escalated_low_probability"
    return "recovered" if row.get("recovered", 0) == 1 else "retry_failed"


def compute_retry_cost(status: str, attempt_number: int) -> float:
    """Returns the operational cost incurred for a given decision."""
    if "escalated" in status:
        return ESCALATION_COST_HUMAN
    # A retry attempt has the per-attempt cost
    return RETRY_COST_PER_ATTEMPT * attempt_number


def compare_batch(audit_df: pd.DataFrame) -> dict:
    """
    Given the audit log (which contains recovery_probability from the ML
    model), compute what WOULD have happened under the rule-based baseline
    and compare to the actual ML outcome.

    Returns a dict with aggregate metrics and per-outcome counts.
    """
    rule_outcomes = []
    ml_outcomes = []
    rule_costs = []
    ml_costs = []

    for _, row in audit_df.iterrows():
        rule_status = rule_based_decision(row)
        ml_status = ml_decision(row, row["recovery_probability"])

        rule_outcomes.append(rule_status)
        ml_outcomes.append(ml_status)

        rule_costs.append(compute_retry_cost(rule_status, row["attempt_number"]))
        ml_costs.append(compute_retry_cost(ml_status, row["attempt_number"]))

    audit_df = audit_df.copy()
    audit_df["rule_status"] = rule_outcomes
    audit_df["ml_status"] = ml_outcomes
    audit_df["rule_cost"] = rule_costs
    audit_df["ml_cost"] = ml_costs

    n = len(audit_df)

    # --- Aggregate counts ---
    rule_recovered = (audit_df["rule_status"] == "recovered").sum()
    ml_recovered = (audit_df["ml_status"] == "recovered").sum()

    rule_escalated = audit_df["rule_status"].str.startswith("escalated").sum()
    ml_escalated = audit_df["ml_status"].str.startswith("escalated").sum()

    # Recoveries ML caught that rules would have stopped (ML advantage)
    ml_caught_rules_missed = (
        (audit_df["ml_status"] == "recovered") &
        (audit_df["rule_status"] == "escalated_max_attempts")
    ).sum()

    # Unnecessary retries rules made that ML avoided (ML saves cost)
    rules_retried_ml_stopped = (
        (audit_df["rule_status"].isin(["recovered", "retry_failed"])) &
        (audit_df["ml_status"] == "escalated_low_probability")
    ).sum()

    # Where both chose to retry but had different outcomes (random noise)
    both_retried = (
        (~audit_df["rule_status"].str.startswith("escalated")) &
        (~audit_df["ml_status"].str.startswith("escalated"))
    ).sum()

    # --- Financial comparison ---
    total_rule_cost = round(audit_df["rule_cost"].sum(), 2)
    total_ml_cost = round(audit_df["ml_cost"].sum(), 2)
    cost_savings = round(total_rule_cost - total_ml_cost, 2)

    rule_recovered_amount = round(
        audit_df.loc[audit_df["rule_status"] == "recovered", "amount"].sum(), 2
    )
    ml_recovered_amount = round(
        audit_df.loc[audit_df["ml_status"] == "recovered", "amount"].sum(), 2
    )

    rule_net = round(rule_recovered_amount - total_rule_cost, 2)
    ml_net = round(ml_recovered_amount - total_ml_cost, 2)
    net_uplift = round(ml_net - rule_net, 2)

    # --- Rate comparison ---
    rule_recovery_rate = round(rule_recovered / n * 100, 1) if n else 0
    ml_recovery_rate = round(ml_recovered / n * 100, 1) if n else 0
    rate_delta = round(ml_recovery_rate - rule_recovery_rate, 1)

    return {
        "total_transactions": n,
        "rule_based": {
            "recovered_count": int(rule_recovered),
            "recovered_amount": rule_recovered_amount,
            "escalated_count": int(rule_escalated),
            "total_operational_cost": total_rule_cost,
            "net_value": rule_net,
            "recovery_rate_percent": rule_recovery_rate,
        },
        "ml_augmented": {
            "recovered_count": int(ml_recovered),
            "recovered_amount": ml_recovered_amount,
            "escalated_count": int(ml_escalated),
            "total_operational_cost": total_ml_cost,
            "net_value": ml_net,
            "recovery_rate_percent": ml_recovery_rate,
        },
        "ml_advantage": {
            "recoveries_ml_caught_rules_missed": int(ml_caught_rules_missed),
            "unnecessary_retries_ml_avoided": int(rules_retried_ml_stopped),
            "operational_cost_savings": cost_savings,
            "net_value_uplift": net_uplift,
            "recovery_rate_delta_pp": rate_delta,
            "verdict": (
                "ML stopping outperforms rule-based on net value"
                if net_uplift > 0
                else "Rule-based marginally ahead on this batch"
            ),
        },
        "cost_assumptions": {
            "retry_cost_per_attempt_inr": RETRY_COST_PER_ATTEMPT,
            "escalation_cost_human_inr": ESCALATION_COST_HUMAN,
        },
    }
