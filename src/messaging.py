"""
Phase 4 (Extended): LLM-powered customer messaging — all 4 directions.

Extended with messages for checkout abandonment, subscription lapsed,
and B2B receivables. Same dual-mode (Ollama / Claude) and caching
architecture as before — at most one LLM call per unique
(root_cause, action) pair regardless of batch size.
"""

import os
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "fallback")  # default to fast fallback; set ollama/claude in .env

# In-memory cache: (root_cause, action) → generated message
_message_cache: dict[str, str] = {}


# ── Fallback messages (used when LLM call fails or provider = fallback) ──

FALLBACK_MESSAGES: dict[str, str] = {
    # Payment failures
    "bank_server_delay": (
        "Hi, your payment couldn't be completed due to a temporary bank "
        "server delay. We're automatically retrying it shortly — no action "
        "needed from your end."
    ),
    "no_money": (
        "Hi, your payment didn't go through due to insufficient balance. "
        "Please retry once you're ready, and we'll process it right away."
    ),
    "user_error": (
        "Hi, your payment failed because the OTP entered was incorrect. "
        "Please try again with the correct OTP to complete your payment."
    ),
    "card_issue": (
        "Hi, your payment failed because your card appears to be expired. "
        "Please update your payment method to continue."
    ),

    # Checkout abandonment
    "checkout_drop": (
        "Hi, we noticed you left something behind! Your cart is saved and "
        "ready whenever you are — complete your order before items sell out."
    ),
    "checkout_friction": (
        "Hi, it looks like you ran into trouble during checkout. We've "
        "applied a special offer to make it easier — tap below to complete "
        "your order."
    ),

    # Subscription lapsed
    "mandate_issue": (
        "Hi, your subscription payment couldn't be processed because your "
        "mandate has expired. Please renew it to continue enjoying uninterrupted access."
    ),
    "subscription_inactive": (
        "Hi, your subscription is currently paused. Reactivate now and we'll "
        "pick up right where you left off — no data lost."
    ),

    # B2B receivables
    "overdue_invoice": (
        "Dear Partner, invoice #{ref} is now overdue. Please find the payment "
        "link attached — reach out if you need any clarifications or a payment plan."
    ),
    "credit_blocked": (
        "Dear Partner, your account has reached its credit limit and new orders "
        "are on hold. Please contact your account manager to review your limit."
    ),
    "dispute_open": (
        "Dear Partner, we've received your dispute and our team is reviewing it. "
        "We'll update you within 2 business days with a resolution."
    ),

    # Fallback
    "unknown": (
        "Hi, your payment couldn't be completed. Please try again, or reach "
        "out to our support team if the issue persists."
    ),
}


PROMPT_TEMPLATE = (
    "A customer's payment or order event failed. Root cause: {root_cause}. "
    "The system has decided this exact action: {action}.\n\n"
    "Write ONE short, natural-sounding message (1-2 sentences) in English "
    "that explains the reason and describes ONLY the action stated above, "
    "phrased the way a real support message would sound — not by literally "
    "restating the action's internal name.\n\n"
    "Examples:\n"
    "root_cause=bank_server_delay, action=retry_after_10_min\n"
    "\"Your payment didn't go through due to a temporary bank server delay. "
    "We're automatically retrying it in the next 10 minutes.\"\n\n"
    "root_cause=checkout_drop, action=send_cart_recovery_email\n"
    "\"You left some items in your cart — they're still saved for you. "
    "Complete your order now before they sell out.\"\n\n"
    "root_cause=mandate_issue, action=request_mandate_renewal\n"
    "\"Your subscription payment failed because your mandate has expired. "
    "Please renew your mandate to continue your subscription.\"\n\n"
    "Now write the message for root_cause={root_cause}, action={action}. "
    "Return only the message text, nothing else."
)


def _call_ollama(prompt: str) -> str:
    import ollama
    response = ollama.chat(
        model="llama3.2:1b",
        messages=[{"role": "user", "content": prompt}]
    )
    return response["message"]["content"].strip()


def _call_claude(prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


def generate_message(root_cause: str, action: str) -> str:
    """Returns a customer-facing message for a given root cause + action.
    Cached per (root_cause, action) pair."""

    cache_key = f"{root_cause}|{action}"
    if cache_key in _message_cache:
        return _message_cache[cache_key]

    prompt = PROMPT_TEMPLATE.format(root_cause=root_cause, action=action)

    try:
        if LLM_PROVIDER == "fallback":
            # Skip LLM entirely — use curated fallback messages directly
            message = FALLBACK_MESSAGES.get(root_cause, FALLBACK_MESSAGES["unknown"])
        elif LLM_PROVIDER == "ollama":
            message = _call_ollama(prompt)
        elif LLM_PROVIDER == "claude":
            message = _call_claude(prompt)
        else:
            raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER}")

        _message_cache[cache_key] = message
        return message

    except Exception as e:
        print(
            f"  [WARN] LLM call failed for '{cache_key}' "
            f"(provider={LLM_PROVIDER}): {e}. Using fallback."
        )
        fallback = FALLBACK_MESSAGES.get(root_cause, FALLBACK_MESSAGES["unknown"])
        _message_cache[cache_key] = fallback
        return fallback


if __name__ == "__main__":
    from src.rules_engine import ROOT_CAUSE_TO_ACTION

    print(f"Testing messaging layer (provider: {LLM_PROVIDER})\n")
    for cause, action in ROOT_CAUSE_TO_ACTION.items():
        msg = generate_message(cause, action)
        print(f"  [{cause} -> {action}]\n  -> {msg}\n")