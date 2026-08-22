"""
Phase 4: LLM-powered customer messaging (cached, minimal cost).

Only used for generating natural-language customer messages — NOT for
any decision-making (root cause, action, or stopping are all handled
by rules_engine.py and train_model.py, which are deterministic/ML).

DUAL MODE:
- LLM_PROVIDER=ollama -> uses local Ollama model (free, for development
  and testing, so no API credits are consumed while iterating on prompts)
- LLM_PROVIDER=claude -> uses Claude API (for the final, deployed version)

Cost control: messages are cached per root_cause. Even in Claude mode,
at most 5 API calls happen ever, regardless of batch size.
"""

import os
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")  # default to free local model

# In-memory cache: root_cause -> generated message
_message_cache = {}

# FALLBACK_MESSAGES = {
#     "bank_server_delay": "Hi! Aapka payment bank server delay ki wajah se fail hua. Hum dobara try kar rahe hain, koi tension nahi.",
#     "no_money": "Hi! Aapka payment insufficient balance ki wajah se fail hua. Jab convenient ho, dobara try kar lijiye.",
#     "user_error": "Hi! Aapka OTP galat gaya, isliye payment fail hua. Please dobara try karein sahi OTP ke saath.",
#     "card_issue": "Hi! Aapka card expire ho chuka hai. Please naya payment method add karein.",
#     "unknown": "Hi! Aapka payment complete nahi ho paya. Please dobara try karein ya support se contact karein.",
# }

# PROMPT_TEMPLATE = (
#     "Ek customer ka payment fail hua hai. Root cause: {root_cause}. "
#     "Ek chhota (2 lines se zyada nahi), friendly, reassuring message likho "
#     "Hinglish mein jo customer ko bataye kya hua aur hum kya kar rahe hain. "
#     "Sirf message do, koi extra explanation nahi."
# )

FALLBACK_MESSAGES = {
    "bank_server_delay": "Hi, your payment couldn't be completed due to a temporary bank server delay. We're automatically retrying it shortly — no action needed from your end.",
    "no_money": "Hi, your payment didn't go through due to insufficient balance. Please retry once you're ready, and we'll process it right away.",
    "user_error": "Hi, your payment failed because the OTP entered was incorrect. Please try again with the correct OTP to complete your payment.",
    "card_issue": "Hi, your payment failed because your card appears to be expired. Please update your payment method to continue.",
    "unknown": "Hi, your payment couldn't be completed. Please try again, or reach out to our support team if the issue persists.",
}

PROMPT_TEMPLATE = (
    "A customer's payment failed. Root cause: {root_cause}. "
    "The system has decided this exact action: {action}.\n\n"
    "Write ONE short, natural-sounding message (1-2 sentences) in English "
    "that explains the reason and describes ONLY the action stated above, "
    "phrased the way a real support message would sound — not by literally "
    "restating the action's internal name.\n\n"
    "Examples:\n"
    "root_cause=bank_server_delay, action=retry_after_10_min\n"
    "\"Your payment didn't go through due to a temporary bank server delay. "
    "We're automatically retrying it in the next 10 minutes.\"\n\n"
    "root_cause=user_error, action=send_otp_help_message\n"
    "\"Your payment failed because the OTP entered didn't match. Please try "
    "again, and check our OTP guide if you're having trouble.\"\n\n"
    "root_cause=card_issue, action=request_new_payment_method\n"
    "\"Your payment failed because your card couldn't be processed. Please "
    "add a new payment method to complete your purchase.\"\n\n"
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
        if LLM_PROVIDER == "ollama":
            message = _call_ollama(prompt)
        elif LLM_PROVIDER == "claude":
            message = _call_claude(prompt)
        else:
            raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER}")

        _message_cache[cache_key] = message
        return message

    except Exception as e:
        print(f"  ⚠️  LLM call failed for '{cache_key}' (provider={LLM_PROVIDER}): {e}. Using fallback.")
        fallback = FALLBACK_MESSAGES.get(root_cause, FALLBACK_MESSAGES["unknown"])
        _message_cache[cache_key] = fallback
        return fallback


if __name__ == "__main__":
    from src.rules_engine import ROOT_CAUSE_TO_ACTION

    print(f"Testing messaging layer (provider: {LLM_PROVIDER})\n")

    for cause, action in ROOT_CAUSE_TO_ACTION.items():
        msg = generate_message(cause, action)
        print(f"  [{cause} -> {action}]\n  -> {msg}\n")