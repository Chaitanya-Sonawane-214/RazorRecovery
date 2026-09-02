"""
API endpoints for serving batch results to the dashboard.
Reads pre-computed results from Phase 5 (run_batch.py output) —
does not re-run the pipeline on every request.
"""

import json
import pandas as pd
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/summary")
def get_summary():
    """Returns the batch-level summary: recovery rate, amounts, breakdown."""
    try:
        with open("data/batch_summary.json", "r") as f:
            summary = json.load(f)
        return summary
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Batch summary not found. Run 'python -m src.run_batch' first."
        )


@router.get("/transactions")
def get_transactions(status: str = None, limit: int = 100):
    """Returns individual transaction records from the audit log.
    Optional 'status' filter (e.g. 'recovered', 'escalated_max_attempts').
    """
    try:
        df = pd.read_csv("data/audit_log.csv")
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Audit log not found. Run 'python -m src.run_batch' first."
        )

    if status:
        df = df[df["final_status"] == status]

    df = df.head(limit)
    return df.to_dict(orient="records")


@router.get("/health")
def health_check():
    return {"status": "ok"}