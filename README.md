# RazorRecovery — AI Revenue Recovery Agent

> Build an agent that detects revenue at risk, determines the right intervention, and executes a bounded recovery workflow.

## What This Does

RazorRecovery is a production-grade AI agent that recovers failed payments and lost revenue across four directions:

| Direction | Examples |
|---|---|
| 💳 **Payment Failure** | UPI timeout, insufficient funds, card expired |
| 🛒 **Checkout Abandonment** | Cart abandoned, checkout friction, promo code failure |
| 🔄 **Subscription Lapsed** | Mandate expired/revoked, subscription paused |
| 🏢 **B2B Receivable** | Overdue invoice, credit limit hit, payment dispute |

For each failed event, the agent:
1. **Diagnoses the root cause** via a rule-based engine
2. **Selects the right recovery action** (retry, reminder, mandate renewal, escalation)
3. **Predicts recovery probability** using an ML classifier (Logistic Regression)
4. **Applies compliant stopping rules** — stops retrying when ML probability < 20% or attempt cap hit
5. **Calls Razorpay test API** for capture/refund on the outcome
6. **Logs a structured explainability record** for every decision

---

## Six Advanced Features

### ⭐ F1 — Real Razorpay Test-Mode API Integration
- Live `capture_payment` and `create_refund` calls via Razorpay REST API
- Samples first 5 transactions per action type with real HTTP calls; rest tagged `live_test_sampled`
- Graceful sandbox fallback when no keys configured
- Badge in dashboard header shows `live_test · rzp_test_XXX...`

### ⚗️ F2 — A/B Comparison: Rule-Based vs ML Stopping
- Runs **both** decision strategies on every transaction
- Quantifies: unnecessary retries avoided, extra recoveries caught, operational cost savings, net value uplift
- Dedicated tab with side-by-side metric cards

### 💰 F3 — Cost / ROI Dashboard
- Gross revenue recovered → gateway fees (2%) → net revenue
- Operational costs: `₹0.50/retry` + `₹5.00/escalation`
- Net ROI %, cost per rupee recovered, break-even recovery rate
- Compared to actual recovery rate — surplus above break-even shown

### 🔍 F4 — Explainability Layer per Decision
- Every audit log entry has a structured `explainability` dict:
  - `decision_path` — ordered list of rule checks
  - `factors` — all numeric inputs to the decision
  - `confidence` — high / medium / low (distance from threshold)
  - `human_readable` — natural language summary
- `GET /api/transactions/{id}/explain` API endpoint
- "🔍 Explain" button per row opens a modal with full decision breakdown + Razorpay response

### 🗺️ F5 — Multiple Recovery Directions
- Architecture generalises across 4 directions, 16 failure codes
- Same `get_root_cause()` / `get_action()` interface — only rules differ
- Per-direction recovery stats in summary and dedicated dashboard tab

### ▶️ F6 — Real-Time Simulation Mode
- `GET /api/simulate/stream` — Server-Sent Events endpoint
- Replays 1,000 transactions live at configurable speed (0.5× / 1× / 2× / 5×)
- Live feed updates in Overview tab; running KPI totals update in real time
- Pause / Resume / Stop controls

---

## Architecture

```
data/
  failed_transactions.csv   # 1000 synthetic transactions, 4 directions
  audit_log.csv             # full pipeline output (1000 rows)
  batch_summary.json        # recovery stats + ROI + A/B snapshot
  ab_comparison.json        # full A/B comparison report

src/
  generate_data.py          # Phase 1: synthetic data (4 directions)
  rules_engine.py           # Phase 2: root cause + action mapping
  train_model.py            # Phase 3: ML stopping model (LogReg)
  messaging.py              # Phase 4: LLM/fallback customer messages
  run_batch.py              # Phase 5: full pipeline orchestrator
  razorpay_client.py        # F1: Razorpay test API wrapper
  ab_comparison.py          # F2: A/B comparison engine
  roi_calculator.py         # F3: cost/ROI calculator

app/
  main.py                   # FastAPI app
  routers/batch.py          # All API endpoints

frontend/
  index.html                # 5-tab dashboard
  style.css                 # Premium dark theme
  script.js                 # All feature logic + SSE simulation

models/
  stopping_model.pkl        # Trained LogisticRegression pipeline
```

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure `.env`
```env
LLM_PROVIDER=fallback          # or ollama / claude
RAZORPAY_KEY_ID=rzp_test_...   # Razorpay test-mode key
RAZORPAY_KEY_SECRET=...
```

### 3. Generate data + train model + run batch
```bash
python -m src.generate_data
python -m src.train_model
python -m src.run_batch
```

### 4. Start the server (with Razorpay keys in env)
```powershell
$env:RAZORPAY_KEY_ID="rzp_test_..."; $env:RAZORPAY_KEY_SECRET="..."; $env:LLM_PROVIDER="fallback"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 5. Open dashboard
```
http://localhost:8000
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/summary` | Batch summary + ROI + A/B snapshot |
| GET | `/api/transactions` | Audit log with filters (status, direction) |
| GET | `/api/transactions/{id}/explain` | Full explainability for one transaction |
| GET | `/api/ab-comparison` | Complete A/B comparison report |
| GET | `/api/razorpay/status` | Razorpay connectivity mode |
| GET | `/api/simulate/stream?speed=1.0` | SSE real-time simulation stream |
| GET | `/api/health` | Health check |

---

## Track Bar Compliance

| Requirement | Implementation |
|---|---|
| Detect revenue at risk | 4 directions, 16 failure codes |
| Determine right intervention | Rule-based engine (deterministic, auditable) |
| Bounded recovery workflow | ML stopping + hard attempt cap (≤3) |
| Measured money recovered across a batch | Summary: count, amount, recovery rate |
| Compliant escalation | Two escalation paths: cap-triggered + probability-triggered |
| Stopping rules | ML threshold (20%) + max attempts (3) |
| Audit trail | 1000-row audit_log.csv with full explainability per row |
