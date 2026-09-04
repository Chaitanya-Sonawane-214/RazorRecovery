# RazorRecovery — Advanced Feature Upgrades

## Background
The base project is complete and meets the track bar:
- Batch pipeline with audit log ✅
- ML stopping rule ✅
- LLM-powered messaging ✅
- FastAPI backend + vanilla JS dashboard ✅

We now add 6 high-impact features that **extend** the existing architecture without violating the track constraints (no external API required to run core pipeline, stays compliant with stopping/escalation rules, audit trail preserved).

---

## Open Questions

> [!IMPORTANT]
> **Do you have a real Razorpay test-mode API key?**
> Feature 1 (Razorpay integration) needs `RAZORPAY_KEY_ID` + `RAZORPAY_KEY_SECRET` from your Razorpay dashboard (test mode). If you don't have them yet, I'll build the full integration with graceful fallback so it works without keys (shows "sandbox mode" badge). The rest of the features work without any API keys.

> [!NOTE]
> **Razorpay integration scope**: In test mode we can call:
> - `POST /v1/payments/{id}/capture` → simulate capturing a payment
> - `POST /v1/refunds` → simulate refund on escalation
> - `GET /v1/payments/{id}` → fetch real payment status
> We'll create a `RazorpayClient` wrapper that falls back to mock responses when keys are absent.

---

## Proposed Changes

### Feature 1 — Real Razorpay Test-Mode API Integration ⭐

The biggest credibility upgrade. Wrap the batch pipeline so that for "recovered" outcomes, we actually call Razorpay's test API to capture the payment — a real API response appears in the audit log.

#### [NEW] `src/razorpay_client.py`
- `RazorpayClient` class wrapping `httpx` (already in requirements)
- Methods: `capture_payment(payment_id, amount)`, `create_refund(payment_id)`, `fetch_payment(payment_id)`
- Falls back gracefully to mock response dict when no keys are configured
- Logs `razorpay_api_response` (real or mock) into audit entry

#### [MODIFY] `src/run_batch.py`
- Import and initialise `RazorpayClient`
- In `process_transaction()`: if `final_status == "recovered"` → call `client.capture_payment()`, attach `razorpay_response` field to audit entry
- If `final_status == "escalated_*"` → call `client.create_refund()` (test mode only)
- Add `razorpay_mode: "live_test" | "sandbox"` field to batch summary

#### [MODIFY] `.env.example`
- Add `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`

#### [MODIFY] `app/routers/batch.py`
- New endpoint `GET /api/razorpay/status` → returns Razorpay connectivity mode

---

### Feature 2 — A/B Comparison: Rule-Based vs ML Stopping

Quantified improvement — runs both decision methods on every transaction and shows the delta. This is the "business case proof" for using ML.

#### [NEW] `src/ab_comparison.py`
- `rule_based_decision(row)` → pure rules: stop if `attempt_number >= MAX_ATTEMPTS`, else retry
- `ml_decision(row, model)` → existing ML logic
- `compare_batch(df, model)` → returns per-transaction comparison + aggregate stats
- Metrics computed:
  - **Unnecessary retries avoided by ML** (rule would retry but ML correctly stopped)
  - **Recoveries ML caught that rules missed** (ML retried when rules would have stopped)
  - **Net uplift in recovery rate** (percentage points)
  - **Estimated cost savings** (retries have a cost: `₹0.50 per attempt` assumption)

#### [NEW] `data/ab_comparison.json` (output artifact)

#### [MODIFY] `app/routers/batch.py`
- New endpoint `GET /api/ab-comparison` → returns the comparison JSON

#### [MODIFY] `frontend/` (dashboard tab)
- New "A/B Comparison" tab in the dashboard showing side-by-side metrics

---

### Feature 3 — Cost/ROI Dashboard

Business-thinking layer: shows revenue recovered, cost of retries, net ROI, and a payback frame.

#### [NEW] `src/roi_calculator.py`
- `RETRY_COST_PER_ATTEMPT = 0.50` (INR, configurable)
- `ESCALATION_COST = 5.00` (human review cost)
- `compute_roi(audit_df, summary)` → returns:
  - `gross_revenue_recovered`
  - `total_retry_cost`
  - `total_escalation_cost`
  - `net_roi`
  - `roi_percent`
  - `cost_per_recovered_rupee`
  - `break_even_recovery_rate`

#### [MODIFY] `src/run_batch.py`
- Call `compute_roi()` after `build_summary()`, embed result in `batch_summary.json` under `"roi"` key

#### [MODIFY] `app/routers/batch.py`
- ROI data already in `/api/summary` (no separate endpoint needed)

#### [MODIFY] `frontend/`
- New "ROI" section in dashboard: cost/revenue bar chart, ROI % prominently displayed

---

### Feature 4 — Explainability Layer (Audit Log "Why")

Already have `reasoning` field, but this formalises it into a structured explainability object — making the audit log genuinely useful for compliance/review.

#### [MODIFY] `src/run_batch.py`
- Replace flat `reasoning` string with structured `explainability` dict:
```json
{
  "decision_path": ["check_attempt_number", "check_ml_probability", "outcome"],
  "factors": {
    "attempt_number": 2,
    "recovery_probability": 0.73,
    "threshold_used": 0.20,
    "stopping_rule_triggered": "ml_below_threshold | max_attempts | none"
  },
  "confidence": "high | medium | low",
  "human_readable": "..."
}
```
- Keep `reasoning` field as alias (backward compat)

#### [MODIFY] `app/routers/batch.py`
- New endpoint `GET /api/transactions/{transaction_id}/explain` → returns full explainability for one transaction

#### [MODIFY] `frontend/`
- Clicking a transaction row shows an "Explain Decision" modal with the structured breakdown

---

### Feature 5 — Multiple Recovery Directions (Generalised Architecture)

Show the architecture handles all the track's "example directions", not just payment failures. Add two more recovery direction types to prove generalisation.

#### [MODIFY] `src/rules_engine.py`
- Add `RECOVERY_DIRECTION` enum: `payment_failure`, `checkout_abandonment`, `subscription_lapsed`, `b2b_receivable`
- Extend `FAILURE_CODE_TO_ROOT_CAUSE` with new codes per direction:
  - Checkout: `CART_ABANDONED`, `CHECKOUT_TIMEOUT`
  - Subscription: `MANDATE_EXPIRED`, `SUBSCRIPTION_PAUSED`
  - B2B: `INVOICE_OVERDUE`, `CREDIT_LIMIT_HIT`
- Each direction has its own action set in `ROOT_CAUSE_TO_ACTION`

#### [MODIFY] `src/generate_data.py`
- Add `direction` field to generated transactions (weighted: 60% payment, 20% checkout, 10% subscription, 10% B2B)

#### [MODIFY] `src/run_batch.py`
- Group audit log by `direction`, compute per-direction recovery stats in summary

#### [MODIFY] `app/routers/batch.py`
- Existing `/api/summary` returns per-direction breakdown (no new endpoint)

#### [MODIFY] `frontend/`
- Direction filter in transaction table; per-direction cards in summary section

---

### Feature 6 — Real-Time Simulation Mode

Engaging live demo: instead of showing pre-computed batch results, the frontend streams transactions being processed one-by-one in real time.

#### [MODIFY] `app/main.py`
- Add `/api/simulate/stream` SSE (Server-Sent Events) endpoint using `StreamingResponse`
- Replays the audit log rows with configurable speed (default: 1 tx/sec)

#### [MODIFY] `app/routers/batch.py`
- New `GET /api/simulate/stream?speed=1.0` endpoint
- Streams each transaction as a JSON event, with a final `summary` event

#### [MODIFY] `frontend/`
- "Live Simulation" button triggers SSE connection
- Transactions appear one-by-one with animation, running totals update in real time
- "Pause / Resume / Reset" controls

---

## Files Changed Summary

| File | Change Type | Feature |
|---|---|---|
| `src/razorpay_client.py` | NEW | F1 |
| `src/ab_comparison.py` | NEW | F2 |
| `src/roi_calculator.py` | NEW | F3 |
| `src/run_batch.py` | MODIFY | F1, F2, F3, F4, F5 |
| `src/rules_engine.py` | MODIFY | F5 |
| `src/generate_data.py` | MODIFY | F5 |
| `src/messaging.py` | MODIFY | F5 (new direction messages) |
| `app/main.py` | MODIFY | F6 |
| `app/routers/batch.py` | MODIFY | F1, F2, F4, F6 |
| `frontend/index.html` | MODIFY | F2, F3, F4, F5, F6 |
| `frontend/style.css` | MODIFY | All frontend features |
| `frontend/script.js` | MODIFY | All frontend features |
| `.env.example` | MODIFY | F1 |
| `data/ab_comparison.json` | NEW | F2 (generated output) |

---

## Track Bar Compliance Check

| Track Requirement | Still Met? |
|---|---|
| Detect revenue at risk | ✅ (expanded with 4 directions) |
| Determine right intervention | ✅ (rules engine extended) |
| Bounded recovery workflow | ✅ (stopping rules unchanged) |
| Measured money recovered across a batch | ✅ (ROI adds cost dimension) |
| Compliant escalation | ✅ (not changed) |
| Stopping rules | ✅ (ML stopping preserved; A/B shows improvement) |
| Audit trail | ✅ (explainability deepens it) |

---

## Verification Plan

### Automated
```bash
# Re-generate data with new directions
python -m src.generate_data

# Retrain model on new data  
python -m src.train_model

# Run full batch (generates audit_log, ab_comparison, roi in one pass)
python -m src.run_batch

# Start server
uvicorn app.main:app --reload

# Check all endpoints
curl http://localhost:8000/api/summary
curl http://localhost:8000/api/ab-comparison
curl http://localhost:8000/api/transactions/TXN10000/explain
curl http://localhost:8000/api/simulate/stream
```

### Manual
- Open dashboard, verify 6 feature sections render correctly
- Click "Live Simulation" — watch transactions stream in real time
- Click a transaction row → "Explain Decision" modal appears
- A/B tab shows rule vs ML delta with numbers

