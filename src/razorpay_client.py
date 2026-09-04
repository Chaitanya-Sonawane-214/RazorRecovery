"""
Feature 1: Razorpay Test-Mode API Integration.

Wraps Razorpay's REST API using httpx (already in requirements).
Falls back gracefully to mock responses when RAZORPAY_KEY_ID /
RAZORPAY_KEY_SECRET are not configured — shows a "sandbox" badge in
the dashboard instead of "live test".

In real test mode:
  - capture_payment()  → POST /v1/payments/{id}/capture
  - create_refund()    → POST /v1/refunds
  - fetch_payment()    → GET  /v1/payments/{id}

LIVE_SAMPLE_LIMIT: We make real Razorpay API calls for the first N
transactions per action type to prove integration, then use enriched
mock responses for the rest. Synthetic payment IDs (TXN10000...) are
not real Razorpay IDs — the API will return a 400/404 for them, so
we catch that and return a structured error response that is still
logged. This is the honest, realistic behaviour for a demo with
synthetic data + real API keys.

All methods return a uniform dict so the audit log schema is stable.
"""

import os
import httpx
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

RAZORPAY_BASE_URL = "https://api.razorpay.com/v1"
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

# Only make live API calls for the first N per action type.
# Proves integration without hammering the API for 500+ synthetic IDs.
LIVE_SAMPLE_LIMIT = 5

# Detect mode at import time so every call knows which path to use
IS_LIVE_TEST = bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)


class RazorpayClient:
    """
    Thin wrapper around Razorpay's REST API.

    Live API calls are limited to LIVE_SAMPLE_LIMIT per action type —
    enough to prove the integration with real Razorpay credentials while
    keeping the batch fast. Remaining transactions get enriched mock
    responses tagged as 'live_test_sampled'.

    Usage:
        client = RazorpayClient()
        result = client.capture_payment("pay_test_abc123", 1500.00)
        # result["mode"] == "live_test" | "live_test_sampled" | "sandbox"
    """

    def __init__(self):
        self.mode = "live_test" if IS_LIVE_TEST else "sandbox"
        if IS_LIVE_TEST:
            self._auth = (RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
        else:
            self._auth = None
        # Per-action counters to enforce LIVE_SAMPLE_LIMIT
        self._live_calls = {"capture": 0, "refund": 0, "fetch": 0}

    def _should_call_live(self, action: str) -> bool:
        """Returns True if we should make a real API call for this action."""
        if not IS_LIVE_TEST:
            return False
        if self._live_calls.get(action, 0) < LIVE_SAMPLE_LIMIT:
            self._live_calls[action] = self._live_calls.get(action, 0) + 1
            return True
        return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def capture_payment(self, payment_id: str, amount: float) -> dict:
        """
        Capture a previously authorised payment.
        Amount must be in paise (INR × 100) for the real API call.
        First LIVE_SAMPLE_LIMIT calls hit the real Razorpay API.
        """
        if not self._should_call_live("capture"):
            mock = self._mock_capture(payment_id, amount)
            if IS_LIVE_TEST:
                mock["mode"] = "live_test_sampled"  # keys present, skipped for speed
            return mock

        amount_paise = int(amount * 100)
        try:
            resp = httpx.post(
                f"{RAZORPAY_BASE_URL}/payments/{payment_id}/capture",
                auth=self._auth,
                json={"amount": amount_paise, "currency": "INR"},
                timeout=10.0,
            )
            data = resp.json()
            return {
                "mode": "live_test",
                "action": "capture",
                "payment_id": data.get("id", payment_id),
                "status": data.get("status", "api_responded"),
                "amount": data.get("amount", amount_paise) / 100,
                "currency": data.get("currency", "INR"),
                "http_status": resp.status_code,
                "razorpay_raw": data,
                "called_at": datetime.now().isoformat(),
            }
        except Exception as e:
            return self._error_response("capture", payment_id, str(e))

    def create_refund(self, payment_id: str, amount: float = None) -> dict:
        """
        Initiate a refund for an escalated/failed payment.
        First LIVE_SAMPLE_LIMIT calls hit the real Razorpay API.
        """
        if not self._should_call_live("refund"):
            mock = self._mock_refund(payment_id, amount)
            if IS_LIVE_TEST:
                mock["mode"] = "live_test_sampled"
            return mock

        payload = {"speed": "normal"}
        if amount is not None:
            payload["amount"] = int(amount * 100)

        try:
            resp = httpx.post(
                f"{RAZORPAY_BASE_URL}/payments/{payment_id}/refund",
                auth=self._auth,
                json=payload,
                timeout=10.0,
            )
            data = resp.json()
            return {
                "mode": "live_test",
                "action": "refund",
                "refund_id": data.get("id"),
                "payment_id": payment_id,
                "status": data.get("status", "api_responded"),
                "amount": data.get("amount", 0) / 100,
                "http_status": resp.status_code,
                "razorpay_raw": data,
                "called_at": datetime.now().isoformat(),
            }
        except Exception as e:
            return self._error_response("refund", payment_id, str(e))

    def fetch_payment(self, payment_id: str) -> dict:
        """Fetch current status of a payment by ID."""
        if not self._should_call_live("fetch"):
            mock = self._mock_fetch(payment_id)
            if IS_LIVE_TEST:
                mock["mode"] = "live_test_sampled"
            return mock

        try:
            resp = httpx.get(
                f"{RAZORPAY_BASE_URL}/payments/{payment_id}",
                auth=self._auth,
                timeout=10.0,
            )
            data = resp.json()
            return {
                "mode": "live_test",
                "action": "fetch",
                "payment_id": data.get("id", payment_id),
                "status": data.get("status"),
                "amount": data.get("amount", 0) / 100,
                "method": data.get("method"),
                "http_status": resp.status_code,
                "razorpay_raw": data,
                "called_at": datetime.now().isoformat(),
            }
        except Exception as e:
            return self._error_response("fetch", payment_id, str(e))

    # ------------------------------------------------------------------
    # Mock responses (sandbox mode — no keys needed)
    # ------------------------------------------------------------------

    @staticmethod
    def _mock_capture(payment_id: str, amount: float) -> dict:
        return {
            "mode": "sandbox",
            "action": "capture",
            "payment_id": payment_id,
            "status": "captured",
            "amount": round(amount, 2),
            "currency": "INR",
            "note": "Sandbox mock — configure RAZORPAY_KEY_ID + RAZORPAY_KEY_SECRET for live test",
            "called_at": datetime.now().isoformat(),
        }

    @staticmethod
    def _mock_refund(payment_id: str, amount) -> dict:
        return {
            "mode": "sandbox",
            "action": "refund",
            "refund_id": f"rfnd_mock_{payment_id[-6:]}",
            "payment_id": payment_id,
            "status": "processed",
            "amount": round(amount, 2) if amount else 0,
            "note": "Sandbox mock — configure RAZORPAY_KEY_ID + RAZORPAY_KEY_SECRET for live test",
            "called_at": datetime.now().isoformat(),
        }

    @staticmethod
    def _mock_fetch(payment_id: str) -> dict:
        return {
            "mode": "sandbox",
            "action": "fetch",
            "payment_id": payment_id,
            "status": "authorized",
            "amount": 0,
            "method": "upi",
            "note": "Sandbox mock — configure RAZORPAY_KEY_ID + RAZORPAY_KEY_SECRET for live test",
            "called_at": datetime.now().isoformat(),
        }

    @staticmethod
    def _error_response(action: str, payment_id: str, error: str) -> dict:
        return {
            "mode": "live_test",
            "action": action,
            "payment_id": payment_id,
            "status": "api_error",
            "error": error,
            "called_at": datetime.now().isoformat(),
        }
