# Feature 5: Extended rules engine — 4 recovery directions.
#
# Original: payment_failure only (5 failure codes).
# Extended: + checkout_abandonment, subscription_lapsed, b2b_receivable.
#
# The architecture is intentionally identical across all directions —
# same get_root_cause() / get_action() interface — to show the agent
# generalises cleanly to any revenue-loss scenario.


# --- Direction constants ---
DIRECTION_PAYMENT = "payment_failure"
DIRECTION_CHECKOUT = "checkout_abandonment"
DIRECTION_SUBSCRIPTION = "subscription_lapsed"
DIRECTION_B2B = "b2b_receivable"

ALL_DIRECTIONS = [
    DIRECTION_PAYMENT,
    DIRECTION_CHECKOUT,
    DIRECTION_SUBSCRIPTION,
    DIRECTION_B2B,
]


# --- Maps raw gateway / event failure codes to human-readable root cause ---
FAILURE_CODE_TO_ROOT_CAUSE = {
    # Payment failures (original)
    "UPI_TIMEOUT":        "bank_server_delay",
    "BANK_SERVER_DOWN":   "bank_server_delay",
    "INSUFFICIENT_FUNDS": "no_money",
    "WRONG_OTP":          "user_error",
    "CARD_EXPIRED":       "card_issue",

    # Checkout abandonment
    "CART_ABANDONED":     "checkout_drop",
    "CHECKOUT_TIMEOUT":   "checkout_drop",
    "SHIPPING_CONFUSION": "checkout_friction",
    "PROMO_INVALID":      "checkout_friction",

    # Subscription lapsed
    "MANDATE_EXPIRED":    "mandate_issue",
    "MANDATE_REVOKED":    "mandate_issue",
    "SUBSCRIPTION_PAUSED":"subscription_inactive",
    "PLAN_UPGRADE_FAILED":"subscription_inactive",

    # B2B receivables
    "INVOICE_OVERDUE":    "overdue_invoice",
    "CREDIT_LIMIT_HIT":   "credit_blocked",
    "PAYMENT_DISPUTE":    "dispute_open",
}


# --- Maps root cause to recommended recovery action ---
ROOT_CAUSE_TO_ACTION = {
    # Payment failures (original)
    "bank_server_delay":    "retry_after_10_min",
    "no_money":             "send_reminder_after_6_hours",
    "user_error":           "send_otp_help_message",
    "card_issue":           "request_new_payment_method",

    # Checkout abandonment
    "checkout_drop":        "send_cart_recovery_email",
    "checkout_friction":    "send_checkout_help_with_coupon",

    # Subscription lapsed
    "mandate_issue":        "request_mandate_renewal",
    "subscription_inactive":"send_reactivation_offer",

    # B2B receivables
    "overdue_invoice":      "send_payment_reminder_with_link",
    "credit_blocked":       "escalate_to_account_manager",
    "dispute_open":         "initiate_dispute_resolution",

    # Fallback
    "unknown":              "escalate_to_human",
}


# --- Which direction does each failure code belong to ---
FAILURE_CODE_TO_DIRECTION = {
    "UPI_TIMEOUT":         DIRECTION_PAYMENT,
    "BANK_SERVER_DOWN":    DIRECTION_PAYMENT,
    "INSUFFICIENT_FUNDS":  DIRECTION_PAYMENT,
    "WRONG_OTP":           DIRECTION_PAYMENT,
    "CARD_EXPIRED":        DIRECTION_PAYMENT,

    "CART_ABANDONED":      DIRECTION_CHECKOUT,
    "CHECKOUT_TIMEOUT":    DIRECTION_CHECKOUT,
    "SHIPPING_CONFUSION":  DIRECTION_CHECKOUT,
    "PROMO_INVALID":       DIRECTION_CHECKOUT,

    "MANDATE_EXPIRED":     DIRECTION_SUBSCRIPTION,
    "MANDATE_REVOKED":     DIRECTION_SUBSCRIPTION,
    "SUBSCRIPTION_PAUSED": DIRECTION_SUBSCRIPTION,
    "PLAN_UPGRADE_FAILED": DIRECTION_SUBSCRIPTION,

    "INVOICE_OVERDUE":     DIRECTION_B2B,
    "CREDIT_LIMIT_HIT":    DIRECTION_B2B,
    "PAYMENT_DISPUTE":     DIRECTION_B2B,
}


def get_root_cause(failure_code: str) -> str:
    """Map a raw failure code to a root cause. Defaults to 'unknown' for
    any failure code not in our mapping, so the pipeline never crashes
    on unexpected input."""
    return FAILURE_CODE_TO_ROOT_CAUSE.get(failure_code, "unknown")


def get_action(root_cause: str) -> str:
    """Map a root cause to a recommended recovery action. Defaults to
    escalation for unknown causes — safest fallback when we're unsure."""
    return ROOT_CAUSE_TO_ACTION.get(root_cause, "escalate_to_human")


def get_direction(failure_code: str) -> str:
    """Return which recovery direction this failure code belongs to."""
    return FAILURE_CODE_TO_DIRECTION.get(failure_code, DIRECTION_PAYMENT)


def process_failure(failure_code: str) -> dict:
    """Convenience function: run all steps and return a full decision."""
    root_cause = get_root_cause(failure_code)
    action = get_action(root_cause)
    direction = get_direction(failure_code)
    return {
        "failure_code": failure_code,
        "direction": direction,
        "root_cause": root_cause,
        "action": action,
    }


if __name__ == "__main__":
    print("Testing extended rules engine:\n")
    test_codes = list(FAILURE_CODE_TO_ROOT_CAUSE.keys()) + ["SOME_UNKNOWN_CODE"]
    for code in test_codes:
        result = process_failure(code)
        print(
            f"  {result['failure_code']:25} [{result['direction']:22}]"
            f"  -> {result['root_cause']:22}  -> {result['action']}"
        )