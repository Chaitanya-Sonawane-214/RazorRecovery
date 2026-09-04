"""
API endpoints for serving batch results to the dashboard.
"""

import json
import math
import asyncio
import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter()


def _clean(obj):
    """Recursively replace NaN / Inf floats with None so JSON never chokes."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(i) for i in obj]
    return obj

# ── Helpers ────────────────────────────────────────────────────────────────

def _load_summary() -> dict:
    try:
        with open("data/batch_summary.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Batch summary not found. Run 'python -m src.run_batch' first."
        )

def _load_audit_df() -> pd.DataFrame:
    try:
        return pd.read_csv("data/audit_log.csv")
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Audit log not found. Run 'python -m src.run_batch' first."
        )

# ── Existing endpoints (preserved) ─────────────────────────────────────────

@router.get("/summary")
def get_summary():
    """Returns the batch-level summary: recovery rate, amounts, ROI, A/B snapshot."""
    return _load_summary()


@router.get("/transactions")
def get_transactions(status: str = None, direction: str = None, limit: int = 1000):
    """
    Returns individual transaction records from the audit log.
    Optional filters: status, direction.
    """
    df = _load_audit_df()

    if status:
        df = df[df["final_status"] == status]
    if direction:
        df = df[df["direction"] == direction] if "direction" in df.columns else df

    df = df.head(limit)

    records = df.to_dict(orient="records")
    cleaned = []
    for r in records:
        row = {}
        for k, v in r.items():
            # Pandas NaN / numpy float NaN → None so JSON serialises cleanly
            if isinstance(v, float) and v != v:
                row[k] = None
            elif k in ("explainability", "razorpay_response") and isinstance(v, str):
                try:
                    row[k] = json.loads(v)
                except Exception:
                    row[k] = v
            else:
                row[k] = v
        cleaned.append(row)
    return _clean(cleaned)


# ── Feature 4: Explainability ───────────────────────────────────────────────

@router.get("/transactions/{transaction_id}/explain")
def explain_transaction(transaction_id: str):
    """
    Returns the full structured explainability dict for a single transaction.
    Used by the 'Explain Decision' modal in the dashboard.
    """
    df = _load_audit_df()
    matches = df[df["transaction_id"] == transaction_id]

    if matches.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction '{transaction_id}' not found in audit log."
        )

    row = matches.iloc[0].to_dict()

    import math

    explain_raw = row.get("explainability")
    if explain_raw is None or (isinstance(explain_raw, float) and math.isnan(explain_raw)):
        explain_dict = {"human_readable": row.get("reasoning", "") or ""}
    elif isinstance(explain_raw, str):
        try:
            explain_dict = json.loads(explain_raw)
        except Exception:
            explain_dict = {"human_readable": row.get("reasoning", "") or ""}
    else:
        explain_dict = explain_raw or {}

    razorpay_raw = row.get("razorpay_response")
    if razorpay_raw is None or (isinstance(razorpay_raw, float) and math.isnan(razorpay_raw)):
        razorpay_dict = None
    elif isinstance(razorpay_raw, str):
        try:
            razorpay_dict = json.loads(razorpay_raw)
        except Exception:
            razorpay_dict = None
    else:
        razorpay_dict = razorpay_raw

    return _clean({
        "transaction_id":     transaction_id,
        "amount":             row.get("amount"),
        "direction":          row.get("direction"),
        "failure_code":       row.get("failure_code"),
        "root_cause":         row.get("root_cause"),
        "recommended_action": row.get("recommended_action"),
        "final_status":       row.get("final_status"),
        "recovery_probability": row.get("recovery_probability"),
        "attempts":           row.get("attempts"),
        "explainability":     explain_dict,
        "razorpay_response":  razorpay_dict,
        "reasoning":          row.get("reasoning"),
        "customer_message":   row.get("customer_message"),
    })


# ── Feature 2: A/B Comparison ──────────────────────────────────────────────

@router.get("/ab-comparison")
def get_ab_comparison():
    """Returns the full A/B comparison report (rule-based vs ML stopping)."""
    try:
        with open("data/ab_comparison.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="A/B comparison data not found. Run 'python -m src.run_batch' first."
        )


# ── Feature 1: Razorpay Status ─────────────────────────────────────────────

@router.get("/razorpay/status")
def get_razorpay_status():
    """Returns Razorpay integration mode and key presence."""
    import os
    from dotenv import load_dotenv
    load_dotenv(override=True)   # always re-read .env so runtime key changes take effect
    key_id = os.getenv("RAZORPAY_KEY_ID", "")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
    has_keys = bool(key_id and key_secret)
    return {
        "mode": "live_test" if has_keys else "sandbox",
        "key_id_prefix": key_id[:12] + "..." if has_keys else None,
        "connected": has_keys,
        "message": (
            f"Connected to Razorpay test mode · {key_id[:12]}..."
            if has_keys
            else "Running in sandbox mode — configure RAZORPAY_KEY_ID + RAZORPAY_KEY_SECRET for live test"
        ),
    }


# ── Feature 6: Real-Time Simulation (SSE) ──────────────────────────────────

@router.get("/simulate/stream")
async def simulate_stream(speed: float = 1.0):
    """
    Server-Sent Events endpoint for real-time batch replay.

    Streams each transaction from the audit log as a JSON event at the
    configured speed (default: 1 transaction/second). Sends a final
    'summary' event when done.

    speed: transactions per second (0.5 = slow, 2.0 = fast)
    """
    df = _load_audit_df()
    delay = max(0.05, 1.0 / max(0.1, speed))  # seconds between events

    async def event_generator():
        # Send total count first so the frontend knows what to expect
        meta = {"type": "meta", "total": len(df)}
        yield f"data: {json.dumps(meta)}\n\n"

        for i, (_, row) in enumerate(df.iterrows()):
            record = row.to_dict()

            # Parse JSON string columns
            for col in ("explainability", "razorpay_response"):
                if col in record and isinstance(record[col], str):
                    try:
                        record[col] = json.loads(record[col])
                    except Exception:
                        pass

            # Replace NaN with None for JSON serialisation
            record = {
                k: (None if (isinstance(v, float) and v != v) else v)
                for k, v in record.items()
            }

            event = {"type": "transaction", "index": i, "data": record}
            yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(delay)

        # Final summary event
        try:
            with open("data/batch_summary.json", "r") as f:
                summary = json.load(f)
        except Exception:
            summary = {}

        yield f"data: {json.dumps({'type': 'summary', 'data': summary})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Health ──────────────────────────────────────────────────────────────────

@router.get("/health")
def health_check():
    return {"status": "ok", "version": "2.0.0"}