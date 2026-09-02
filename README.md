# 💰 RazorRecovery

<!-- > An AI-powered payment recovery agent — built with **FastAPI** 🚀, **scikit-learn** 🤖, and a **vanilla HTML/CSS/JS** frontend -->

*An independent project built for Razorpay's AI Buildathon 2026 — Track 3: AI Revenue Recovery*

RazorRecovery detects why a payment failed, decides the right recovery action using rule-based logic, uses a small ML model to judge whether retrying is worth it, and generates a human-friendly recovery message — then reports how much money was recovered across a batch, with a full audit trail. 💪

---

## ✨ Features

- 🔍 Rule-based root-cause detection for failed payments (bank delay, insufficient funds, wrong OTP, expired card, bank server down)
- 🎯 Rule-based recovery action selector (retry now, retry later, escalate)
- 🤖 ML-powered stopping rule — a trained classifier predicts recovery probability and decides whether to keep retrying or escalate immediately
- 💬 AI-generated customer recovery messages, action-grounded to prevent hallucination
- 📝 Full audit trail — every decision logged with reasoning
- 📊 Live dashboard — recovery rate, rupees recovered, filterable transaction breakdown
- 🧪 Tested end-to-end on 600 synthetic failed-payment transactions

---

## 📊 Results (from a 600-transaction synthetic batch)

| Metric | Value |
|---|---|
| Transactions processed | 600 |
| Total amount at risk | ₹46,71,039 |
| **Recovery rate** | **37.2%** |
| **Rupees recovered** | **₹16,78,471** |
| Escalated without wasting a retry (ML-predicted low probability) | 75 txns, ₹5,71,331 |
| Stopping-model precision / recall | 58% / 58% |

*75 transactions were escalated on the first attempt — based on the ML model predicting low recovery probability — instead of going through the full retry cycle. This demonstrates the value of case-specific stopping decisions over a fixed "retry N times" rule.*

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| ⚡ Backend Framework | FastAPI |
| 🤖 ML Model | scikit-learn (Logistic Regression) |
| 📦 Data Handling | pandas |
| 🎭 Synthetic Data | Faker |
| 🧠 LLM (messaging only) | Ollama (dev) / Groq / Claude API — pluggable via env var |
| 🎨 Frontend | HTML, CSS, JavaScript (vanilla) |
| 🔐 Secrets Management | python-dotenv |

---

## 📁 Project Structure
```bash
RazorRecovery/
├── data/
│ ├── failed_transactions.csv               # synthetic dataset (600 transactions)
│ ├── audit_log.csv                         # full decision log, one row per transaction
│ └── batch_summary.json                    # aggregated batch results
├── src/
│ ├── generate_data.py                      # synthetic data generator
│ ├── rules_engine.py                       # root cause + action selector (deterministic)
│ ├── train_model.py                        # ML stopping-rule model
│ ├── messaging.py                          # multi-provider LLM messaging (cached)
│ ├── prompt_testing.py                     # prompt experimentation (dev only)
│ └── run_batch.py                          # full pipeline + batch report
├── models/
│ └── stopping_model.pkl                    # trained model (gitignored)
├── app/
│ ├── main.py                               # FastAPI entry point
│ └── routers/
│ └── batch.py                              # API endpoints
├── frontend/
│ ├── index.html
│ ├── style.css
│ └── script.js
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```


---

## 🧠 Architecture
```bash
Failed payment
│
▼
Root cause detection (rule-based)
│
▼
Action selector (rule-based)
│
▼
ML recovery-probability model ──► Stop or continue?
│
▼
Cached LLM message (1 call per unique root_cause + action)
│
▼
Audit log entry ──► Batch report (₹ recovered, recovery rate)
```


---

## 🧠 Why This Design

**Root cause detection and action selection are deterministic (rule-based)** — payment recovery needs consistent, explainable decisions. An LLM making these calls would be unpredictable, which isn't acceptable when real money is involved.

**The ML model handles only the stopping decision** — predicting whether a specific transaction pattern is worth retrying — because that's a genuine pattern-learning problem, not a fixed business rule. It replaces a naive "retry 3 times then stop" rule with a case-specific one: low-probability transactions are escalated immediately instead of wasting retry cycles.

**The LLM is used only for customer-facing messaging**, and cached per (root_cause, action) pair — at most ~20 calls total, regardless of batch size. Early testing with a small local model revealed it would occasionally hallucinate actions not actually taken (e.g. inventing a refund). We fixed this by explicitly grounding the prompt with the system's actual decision, and added refusal-detection with automatic fallback to static messages — a small example of why constrained LLM output is safer than LLM-driven decisions in a financial context.

---

## 🚀 Running Locally

### ✅ Prerequisites
- 🐍 Python 3.10+
- Ollama installed locally (for free dev-mode messaging), or a Groq/Claude API key

### 1️⃣ Clone the repository
```bash
git clone https://github.com/YOUR-USERNAME/razor-recovery.git
cd razor-recovery
```

### 2️⃣ Create and activate a virtual environment
```bash
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # Mac/Linux
```

### 3️⃣ Install dependencies
```bash
pip install -r requirements.txt
```

### 4️⃣ Set up environment variables
Copy `.env.example` to `.env`:
```env
LLM_PROVIDER=ollama
GROQ_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
```

### 5️⃣ Run the pipeline, step by step
```bash
python src/generate_data.py      # generate synthetic transactions
python -m src.train_model        # train the stopping-rule model
python -m src.messaging          # test the messaging layer
python -m src.run_batch          # run the full batch, produce reports
```

### 6️⃣ Launch the dashboard
```bash
uvicorn app.main:app --reload
```
Open **http://127.0.0.1:8000**

---

## ⚠️ Honest Limitations

- Execution is **simulated** — not connected to a real Razorpay test-mode API
- Dataset is **synthetic**, with hand-designed recovery-probability patterns per failure type; the ML model should be read as a learned prior demonstrating case-specific decision-making, not a validated predictor. Retraining on real transaction history would require no pipeline changes, only a new input CSV
- Development used a small local LLM (Ollama) to avoid consuming API credits while iterating on prompts. The final prompt was manually validated against Claude directly, confirming accurate, hallucination-free output — the production version is designed to switch providers via a single environment variable
- The stopping-rule model is trained on synthetic data with hand-designed
  recovery patterns (65% accuracy, 58% precision/recall on held-out data).
  It should be read as a learned prior demonstrating case-specific
  decision-making, not a validated predictor — the architecture would
  need no changes to retrain on real transaction history.
- Early testing revealed the LLM would occasionally hallucinate actions (e.g., inventing a refund that wasn't part of the system's decision). We fixed this by explicitly grounding the prompt with the exact action chosen by the rule-based engine, preventing the LLM from inventing unauthorized actions — a real example of why deterministic decision-making + constrained LLM output is safer than LLM-driven decisions for financial systems.

---

## 🗺️ What I'd Build Next

- Real Razorpay test-mode API integration for actual retry execution
- Additional recovery directions (checkout drop-off, failed subscriptions)
- Cost/ROI tracking alongside recovery amount
- Real-time streaming mode instead of static batch runs

---

## 🗺️ Roadmap

- [x] 1️⃣ Project setup + synthetic data generator 🎭
- [x] 2️⃣ Rule-based root cause + action engine 🎯
- [x] 3️⃣ ML stopping-rule model 🤖
- [x] 4️⃣ LLM messaging layer 💬
- [x] 5️⃣ Audit log + batch runner 📝
- [x] 6️⃣ FastAPI backend + dashboard 📊
- [x] 7️⃣ Documentation + polish 📚

**Progress: 7/7 phases complete — 🎉**

---

## 👨‍💻 Author

**Chaitanya Sonawane**
- Built for Razorpay's AI Buildathon 2026 🚀

