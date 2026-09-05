"""
Phase 4 (Extended): LLM-powered customer messaging — all 4 directions.

Extended with messages for checkout abandonment, subscription lapsed,
and B2B receivables. Provider priority: gemini → ollama → claude → fallback.
At most one LLM call per unique (root_cause, action) pair (cached).

Gemini Flash (free tier: 1500 req/day) is the recommended provider.
Set GEMINI_API_KEY in .env and LLM_PROVIDER=gemini.
"""

import os
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "fallback")  # gemini / ollama / claude / fallback

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


GEMINI_TIMEOUT_SECONDS = 15  # fail fast → fallback if network is slow


def _gemini_api_call(prompt: str) -> str:
    """Inner call — runs in a thread so we can enforce a hard timeout."""
    from google import genai
    from google.genai import types
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in .env")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="models/gemini-flash-latest",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=150,
        ),
    )
    # response.text may be None for thinking models — extract from parts
    if response.text:
        return response.text.strip()
    for candidate in (response.candidates or []):
        for part in (getattr(candidate.content, "parts", None) or []):
            text = getattr(part, "text", None)
            if text:
                return text.strip()
    raise ValueError("Gemini returned no text content")


def _call_gemini(prompt: str) -> str:
    """Call Google Gemini Flash with a hard timeout.
    Free tier: 1500 requests/day. Falls back gracefully if network is slow."""
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_gemini_api_call, prompt)
        try:
            return future.result(timeout=GEMINI_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(
                f"Gemini did not respond within {GEMINI_TIMEOUT_SECONDS}s"
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


# ── Hinglish prompt (for payment_failure direction — addresses track example) ──

HINGLISH_PROMPT_TEMPLATE = (
    "A customer's payment failed. Root cause: {root_cause}. "
    "Recommended action: {action}.\n\n"
    "Write ONE short, warm message in Hinglish (mix of Hindi and English) "
    "as a support SMS/WhatsApp message would sound — 1-2 sentences max. "
    "Be friendly, natural, and clear about what the customer should do next.\n\n"
    "Example: root_cause=insufficient_funds, action=send_reminder_after_6_hours\n"
    "\"Aapka payment balance kam hone ki wajah se fail ho gaya. "
    "Thodi der mein dobara try karein — hum aapki madad ke liye hain! 😊\"\n\n"
    "Now write a Hinglish message for root_cause={root_cause}, action={action}. "
    "Return only the message text, nothing else."
)

# Payment-failure root causes that get a Hinglish variant
_PAYMENT_ROOT_CAUSES = {
    "bank_server_delay", "no_money", "user_error", "card_issue"
}


def generate_message(root_cause: str, action: str, hinglish: bool = False) -> str:
    """Returns a customer-facing message for a given root cause + action.

    Args:
        root_cause: Root cause string from rules_engine.
        action:     Recommended action string from rules_engine.
        hinglish:   If True and root_cause is a payment failure,
                    returns a Hinglish variant (uses LLM if available).

    Cached per (root_cause, action, hinglish) triple.
    """
    cache_key = f"{root_cause}|{action}|{'hi' if hinglish else 'en'}"
    if cache_key in _message_cache:
        return _message_cache[cache_key]

    # Choose the right prompt
    if hinglish and root_cause in _PAYMENT_ROOT_CAUSES:
        prompt = HINGLISH_PROMPT_TEMPLATE.format(root_cause=root_cause, action=action)
    else:
        prompt = PROMPT_TEMPLATE.format(root_cause=root_cause, action=action)

    try:
        if LLM_PROVIDER == "fallback":
            # Skip LLM entirely — use curated fallback messages directly
            message = FALLBACK_MESSAGES.get(root_cause, FALLBACK_MESSAGES["unknown"])
        elif LLM_PROVIDER == "gemini":
            message = _call_gemini(prompt)
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
        print(f"  [{cause} -> {action}]\n  EN: {msg}")
        # Show Hinglish variant for payment root causes
        if cause in _PAYMENT_ROOT_CAUSES:
            hi_msg = generate_message(cause, action, hinglish=True)
            print(f"  HI: {hi_msg}")
        print()