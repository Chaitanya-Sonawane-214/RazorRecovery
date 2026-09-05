# 💰 RazorRecovery — AI Revenue Recovery Agent

> Built for Razorpay's AI Buildathon 2026 — Track 3: AI Revenue Recovery

**RazorRecovery** detects revenue at risk, diagnoses why it's slipping away, decides the right recovery action, and executes a bounded, auditable recovery workflow — across four real revenue-loss scenarios, not just one.

🎥 **[Watch the 5-minute pitch video](https://drive.google.com/file/d/17Jb8AKmyDJ8bt7sD12iwJxCQK5_ChL6L/view?usp=sharing)**

---

## What This Does

For every failed payment, abandoned checkout, lapsed subscription, or overdue B2B invoice, the agent:

| Step | How |
|---|---|
| 1. Diagnose root cause | Rule-based engine — deterministic, auditable |
| 2. Select recovery action | Rule-based mapping (retry, reminder, mandate renewal, escalation) |
| 3. Predict recovery probability | ML classifier (Logistic Regression) |
| 4. Decide: retry or stop | ML threshold (20%) + hard attempt cap (3) — whichever triggers first |
| 5. Execute | Real Razorpay test-mode API call (capture / refund) |
| 6. Log | Structured, explainable audit entry — every decision is traceable |

| Direction | Examples |
|---|---|
| 💳 Payment Failure | UPI timeout, insufficient funds, expired card |
| 🛒 Checkout Abandonment | Cart abandoned, checkout friction, invalid promo |
| 🔄 Subscription Lapsed | Mandate expired/revoked, subscription paused |
| 🏢 B2B Receivable | Overdue invoice, credit limit hit, payment dispute |

---

## 📊 Results (1,000-transaction synthetic batch)

| Metric | Value |
|---|---|
| Transactions processed | 1,000 (across 4 directions, 16 failure codes) |
| Total amount at risk | ₹3,04,76,038 |
| **Recovery rate** | **34.9%** |
| **Revenue recovered** | **₹97,92,603** |
| Operational cost (retries + escalations) | ₹2,204 |
| **Cost efficiency** | **0.023%** of recovered revenue |
| Net value after costs | ₹95,94,547 |
| Stopping-model precision / recall | 74% / 48% (up from 58%/58% on the original single-direction dataset) |

### A/B: Rule-based vs ML-augmented stopping

| | Rule-based (retry-until-cap) | ML-augmented |
|---|---|---|
| Recovery rate | 35.1% | 34.9% |
| Unnecessary retries avoided | 0 | **92** |

ML-augmented stopping shows a **marginal recovery-rate tradeoff (-0.2pp)** on this synthetic batch — a direct consequence of the model's 74%/48% precision/recall: some genuinely-recoverable transactions get escalated early because the model isn't perfectly confident. In exchange, it avoids 92 retries on transactions it correctly judged unlikely to recover, reducing customer friction and wasted attempts. With a higher-precision model — realistic once trained on real transaction history instead of synthetic data — we'd expect this tradeoff to shrink or disappear while keeping the friction-reduction benefit. We're reporting this honestly rather than tuning the numbers to look better.

---

## 🧠 Why This Design

**Root cause detection and action selection are deterministic (rule-based)**, not LLM-driven. Payment recovery needs consistent, explainable decisions — an LLM choosing actions would be unpredictable, which isn't acceptable when real money is involved.

**The ML model handles only the stopping decision** — whether a specific transaction pattern is worth retrying. This is a genuine pattern-learning problem, unlike root cause/action which are fixed business policy. It replaces a naive "retry 3 times then stop" rule with a case-specific one.

**The LLM is used only for customer-facing messaging**, and cached per (root_cause, action) pair — at most ~20 calls total regardless of batch size. During development, a small local model (Ollama) occasionally hallucinated actions that weren't actually taken (e.g. inventing a refund) — we fixed this by explicitly grounding the prompt with the system's real decision, and added refusal-detection with automatic fallback to static messages.

**Final submission runs with `LLM_PROVIDER=fallback`** — curated, human-written messages instead of a live LLM call. This was a deliberate choice: local models were too slow for a smooth demo, and we didn't want to depend on paid API credits for a component that isn't the core decision-making logic. The prompt was manually validated against Claude directly and confirmed to produce accurate, hallucination-free output — the code supports switching to `ollama` or `claude` via a single environment variable with no other changes.

**Cost/ROI numbers are reported as cost-efficiency (% of revenue), not a raw ROI ratio.** An earlier version computed `net_gain / operational_cost`, which produced a meaningless 400,000%+ figure once we noticed it — because operational cost (₹0.50/retry) is trivially small next to revenue recovered (lakhs). We caught and fixed this before submission rather than presenting an inflated number.

---

## 🏗️ Architecture
```bash
Failed event (payment / checkout / subscription / B2B)
│
▼
Root cause detection (rule-based)
│
▼
Action selector (rule-based)
│
▼
ML recovery-probability model ──► Stop or continue?
│ │
▼ ▼
Razorpay API call Escalate (compliant,
(capture / refund) logged, bounded)
│
▼
Structured explainability + audit log entry
│
▼
Batch report (₹ recovered, recovery rate, A/B, ROI)
```

---

## ✨ Features

**Core pipeline**
- Rule-based root-cause detection and recovery-action selection
- ML-powered stopping rule (Logistic Regression, trained on synthetic data)
- LLM/fallback customer messaging, action-grounded to prevent hallucination
- Full audit trail with structured, per-decision explainability

**Extended (post-core-completion additions)**
- ⭐ Real Razorpay test-mode API integration — live `capture`/`refund` calls, sampled (5 per action type) to prove integration without hammering the API on synthetic IDs
- ⚗️ A/B comparison: rule-based vs ML stopping, with cost and recovery-rate deltas
- 💰 Cost/ROI breakdown: gross revenue → gateway fees → net revenue → operational cost → net value
- 🔍 Structured explainability: decision path, factors, confidence tier, human-readable summary per transaction
- 🗺️ 4 recovery directions, 16 failure codes, same rules-engine interface throughout
- ▶️ Real-time simulation mode (Server-Sent Events) — replays the batch live with pause/resume/speed controls

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI |
| ML | scikit-learn (Logistic Regression) |
| Data | pandas, Faker (synthetic generation) |
| Payments | Razorpay REST API (test mode, via httpx) |
| LLM (optional) | Ollama / Claude — pluggable via `LLM_PROVIDER` |
| Frontend | HTML, CSS, JavaScript (vanilla), Server-Sent Events |
| Secrets | python-dotenv |

---

## 📁 Project Structure
```bash
RazorRecovery/
├── data/
│ ├── failed_transactions.csv               # 1,000 synthetic transactions, 4 directions
│ ├── audit_log.csv                         # full decision log, 1 row per transaction
│ ├── batch_summary.json                    # recovery stats + ROI + A/B snapshot
│ └── ab_comparison.json                    # full A/B comparison report
├── src/
│ ├── generate_data.py                      # synthetic data generator (4 directions)
│ ├── rules_engine.py                       # root cause + action + direction mapping
│ ├── train_model.py                        # ML stopping-rule model
│ ├── messaging.py                          # LLM/fallback customer messaging (cached)
│ ├── razorpay_client.py                    # Razorpay test-mode API wrapper
│ ├── ab_comparison.py                      # rule-based vs ML comparison engine
│ └── run_batch.py                          # full pipeline orchestrator
├── models/
│ └── stopping_model.pkl                    # trained model (gitignored)
├── app/
│ ├── main.py                               # FastAPI entry point
│ └── routers/batch.py                      # all API endpoints
├── frontend/
│ ├── index.html                            # multi-tab dashboard
│ ├── style.css
│ └── script.js
├── requirements.txt
├── .env.example
└── README.md
```


---

## 🚀 Running Locally

### Prerequisites
- Python 3.10+
- Razorpay test-mode API keys (optional — runs in sandbox mode without them)

### Setup
```bash
git clone <YOUR_GITHUB_URL>
cd razor-recovery
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Mac/Linux
pip install -r requirements.txt
```

### Configure `.env`
```env
LLM_PROVIDER=fallback
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
```

### Run the pipeline
```bash
python -m src.generate_data
python -m src.train_model
python -m src.run_batch
```

### Launch the dashboard
```bash
uvicorn app.main:app --reload
```
Open **http://127.0.0.1:8000**

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/summary` | Batch summary + ROI + A/B snapshot |
| GET | `/api/transactions` | Audit log, filterable by status/direction |
| GET | `/api/transactions/{id}/explain` | Full structured explainability for one transaction |
| GET | `/api/ab-comparison` | Complete A/B comparison report |
| GET | `/api/razorpay/status` | Razorpay connectivity mode |
| GET | `/api/simulate/stream?speed=1.0` | SSE live simulation replay |
| GET | `/api/health` | Health check |

---

## ✅ Track Bar Compliance

| Requirement | Implementation |
|---|---|
| Detect revenue at risk | 4 directions, 16 failure codes |
| Determine right intervention | Deterministic, auditable rules engine |
| Bounded recovery workflow | ML stopping threshold + hard attempt cap (≤3) |
| Measured money recovered across a batch | ₹97,92,603 recovered of ₹3,04,76,038 at risk (34.9%) |
| Compliant escalation | Two escalation paths — attempt cap and low predicted probability — both logged |
| Stopping rules | ML threshold (20%) + max attempts (3), never unbounded |
| Audit trail | 1,000-row audit log, structured explainability per decision |

---

## ⚠️ Honest Limitations

- **Dataset is synthetic** with hand-designed recovery-probability patterns per failure code. The ML model should be read as a learned prior demonstrating case-specific decision-making, not a validated predictor — no pipeline changes would be needed to retrain on real transaction history.
- **A/B comparison shows a small ML recovery-rate tradeoff (-0.2pp)** on this batch, a direct effect of the model's 74%/48% precision/recall. We report this honestly rather than adjusting the model or cost assumptions to produce a more favorable-looking number.
- **Razorpay execution is real but sampled** — the first 5 transactions per action type make genuine test-mode API calls (visible in the audit log's `razorpay_response` field); the remainder use enriched mock responses to keep the batch fast, since synthetic transaction IDs aren't real Razorpay payment IDs.
- **Final submission uses `LLM_PROVIDER=fallback`** (curated static messages) rather than a live LLM call, for demo reliability and to avoid API cost/latency during development. The prompt was manually validated against Claude and confirmed accurate — switching providers requires only an environment variable change.
- **No persistent database** — results are file-based (CSV/JSON), regenerated by re-running the batch. Sufficient for this batch-oriented use case; a production system would need a database and a job scheduler.

---

## 🗺️ What's Next

- Full (non-sampled) Razorpay integration once beyond test-mode rate limits
- Real transaction history to retrain the stopping model and validate the A/B tradeoff
- Live retry scheduling instead of batch simulation
- Additional recovery directions (e.g. mandate retry sequencing, promise-to-pay tracking)

---

## 👨‍💻 Author

**Chaitanya Sonawane**
Built for Razorpay's AI Buildathon 2026 🚀