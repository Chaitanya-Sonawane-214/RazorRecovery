"""
Feature 3: Cost / ROI Calculator.

Turns raw recovery numbers into business metrics: gross revenue recovered,
operational cost of all retries + escalations, net ROI, and the break-even
recovery rate the system needs to reach to justify its cost.

These numbers are what a finance/product audience will actually care about —
"you recovered ₹X but spent ₹Y getting there, so the real gain is ₹Z."
"""

import pandas as pd

# --- Cost model (INR, configurable via arguments if needed) ---
RETRY_COST_PER_ATTEMPT: float = 0.50    # SMS/WhatsApp + gateway overhead per retry
ESCALATION_COST_HUMAN: float = 5.00     # Cost of routing to human review queue
SYSTEM_FIXED_COST_PER_BATCH: float = 0  # Cloud/infra cost if relevant (set 0 for demo)

# Razorpay's actual payment gateway fee (approx 2% of recovered amount)
GATEWAY_FEE_PERCENT: float = 0.02


def compute_roi(audit_df: pd.DataFrame) -> dict:
    """
    Computes the full cost/revenue breakdown for a completed batch.

    Parameters
    ----------
    audit_df : pd.DataFrame
        The full audit log produced by run_batch.run_batch().
        Must contain: final_status, amount, attempt_number columns.

    Returns
    -------
    dict
        ROI metrics ready to embed in batch_summary.json and serve to the
        dashboard.
    """
    n = len(audit_df)

    # --- Revenue side ---
    recovered_df = audit_df[audit_df["final_status"] == "recovered"]
    gross_revenue_recovered = round(recovered_df["amount"].sum(), 2)

    # Gateway takes its cut on successful captures
    gateway_fees = round(gross_revenue_recovered * GATEWAY_FEE_PERCENT, 2)
    net_revenue_recovered = round(gross_revenue_recovered - gateway_fees, 2)

    # --- Cost side ---
    # Every transaction incurs retry cost proportional to attempts made
    total_retry_cost = round(
        audit_df["attempt_number"].sum() * RETRY_COST_PER_ATTEMPT, 2
    )

    # Escalated transactions incur human-review cost
    escalated_count = audit_df["final_status"].str.startswith("escalated").sum()
    total_escalation_cost = round(int(escalated_count) * ESCALATION_COST_HUMAN, 2)

    total_operational_cost = round(
        total_retry_cost + total_escalation_cost + SYSTEM_FIXED_COST_PER_BATCH, 2
    )

    # --- Net ROI ---
    # net_roi = round(net_revenue_recovered - total_operational_cost, 2)
    # roi_percent = (
    #     round(net_roi / total_operational_cost * 100, 1)
    #     if total_operational_cost > 0 else 0
    # )

    net_roi = round(net_revenue_recovered - total_operational_cost, 2)
    cost_efficiency_percent = (
        round(total_operational_cost / gross_revenue_recovered * 100, 3)
        if gross_revenue_recovered > 0 else 0
    )

    # Cost efficiency: how many paise spent per rupee recovered
    cost_per_recovered_rupee = (
        round(total_operational_cost / gross_revenue_recovered, 4)
        if gross_revenue_recovered > 0 else None
    )

    # Break-even: minimum recovery rate to cover operational costs
    avg_transaction_amount = round(audit_df["amount"].mean(), 2) if n > 0 else 0
    break_even_count = (
        int((total_operational_cost / avg_transaction_amount) + 1)
        if avg_transaction_amount > 0 else 0
    )
    break_even_recovery_rate_percent = (
        round(break_even_count / n * 100, 1) if n > 0 else 0
    )

    # --- Per-direction breakdown if direction column exists ---
    per_direction = {}
    if "direction" in audit_df.columns:
        for direction, group in audit_df.groupby("direction"):
            dir_recovered = group[group["final_status"] == "recovered"]
            dir_gross = round(dir_recovered["amount"].sum(), 2)
            dir_cost = round(
                group["attempt_number"].sum() * RETRY_COST_PER_ATTEMPT +
                group["final_status"].str.startswith("escalated").sum() * ESCALATION_COST_HUMAN,
                2
            )
            per_direction[direction] = {
                "gross_revenue_recovered": dir_gross,
                "operational_cost": dir_cost,
                "net_roi": round(dir_gross - dir_cost, 2),
                "transaction_count": len(group),
            }

    return {
        "revenue": {
            "gross_recovered": gross_revenue_recovered,
            "gateway_fees": gateway_fees,
            "net_recovered": net_revenue_recovered,
        },
        "costs": {
            "retry_cost": total_retry_cost,
            "escalation_cost": total_escalation_cost,
            "total_operational_cost": total_operational_cost,
        },
        "roi": {
            "net_roi": net_roi,
            # "roi_percent": roi_percent,
            "cost_efficiency_percent": cost_efficiency_percent,
            "cost_per_recovered_rupee": cost_per_recovered_rupee,
        },
        "break_even": {
            "min_recoveries_needed": break_even_count,
            "break_even_recovery_rate_percent": break_even_recovery_rate_percent,
            "actual_recovery_rate_percent": round(
                len(recovered_df) / n * 100, 1
            ) if n > 0 else 0,
        },
        "per_direction": per_direction,
        "cost_assumptions": {
            "retry_cost_per_attempt_inr": RETRY_COST_PER_ATTEMPT,
            "escalation_cost_human_inr": ESCALATION_COST_HUMAN,
            "gateway_fee_percent": GATEWAY_FEE_PERCENT,
        },
    }
