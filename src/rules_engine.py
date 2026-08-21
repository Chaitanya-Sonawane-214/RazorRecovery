# Maps raw payment-gateway failure codes to a human-readable root cause
FAILURE_CODE_TO_ROOT_CAUSE = {
    "UPI_TIMEOUT": "bank_server_delay",
    "BANK_SERVER_DOWN": "bank_server_delay",
    "INSUFFICIENT_FUNDS": "no_money",
    "WRONG_OTP": "user_error",
    "CARD_EXPIRED": "card_issue",
}

# Maps root cause to the recommended recovery action
ROOT_CAUSE_TO_ACTION = {
    "bank_server_delay": "retry_after_10_min",
    "no_money": "send_reminder_after_6_hours",
    "user_error": "send_otp_help_message",
    "card_issue": "request_new_payment_method",
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


def process_failure(failure_code: str) -> dict:
    """Convenience function: run both steps and return a full decision."""
    root_cause = get_root_cause(failure_code)
    action = get_action(root_cause)
    return {
        "failure_code": failure_code,
        "root_cause": root_cause,
        "action": action,
    }


if __name__ == "__main__":
    # Quick manual test — run this file directly to sanity-check all
    # known failure codes map correctly.
    test_codes = [
        "UPI_TIMEOUT",
        "INSUFFICIENT_FUNDS",
        "WRONG_OTP",
        "CARD_EXPIRED",
        "BANK_SERVER_DOWN",
        "SOME_UNKNOWN_CODE",  # tests the fallback path
    ]

    print("Testing rules engine:\n")
    for code in test_codes:
        result = process_failure(code)
        print(f"  {result['failure_code']:20} -> {result['root_cause']:20} -> {result['action']}")