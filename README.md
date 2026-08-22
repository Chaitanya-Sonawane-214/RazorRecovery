# 💰 RazorRecovery

> An AI-powered payment recovery agent — built with **Python** 🐍, **scikit-learn** 🤖 and **LLM API** 🧠

*An independent project built for Razorpay's AI Buildathon 2026 — Track 3: AI Revenue Recovery*

RazorRecovery detects why a payment failed, decides the right recovery action using rule-based logic, uses a small ML model to judge whether retrying is worth it, and generates a human-friendly recovery message — then reports how much money was recovered across a batch, with a full audit trail. 💪

---

## 🌐 Live Demo

- 🎨 **Dashboard**: [link once deployed]
- 📊 **Sample batch report**: [link once available]

> ⚠️ [Add hosting notes here once deployed]

---

## ✨ Features

- 🔍 Rule-based root-cause detection for failed payments (timeout, insufficient funds, wrong OTP, expired card, bank server down)
- 🎯 Rule-based recovery action selector (retry now, retry later, escalate)
- 🤖 ML-powered stopping rule — a trained classifier predicts recovery probability and decides whether to keep retrying or escalate
- 💬 AI-generated customer recovery messages (Hinglish), cached per failure type to control cost
- 📝 Full audit trail — every decision logged with reasoning
- 📊 Batch-level dashboard — recovery rate, rupees recovered, transaction breakdown
- 🧪 Tested on 600 synthetic failed-payment transactions

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| 🐍 Core Language | Python |
| 🤖 ML Model | scikit-learn (Logistic Regression) |
| 📦 Data Handling | pandas |
| 🎭 Synthetic Data | Faker |
| 🧠 LLM (messaging only) | Claude API (Anthropic) |
| 🎨 Dashboard | Streamlit |
| 🔐 Secrets Management | python-dotenv |

---

## 📁 Project Structure

```bash
RazorRecovery/
├── data/
│   ├── .gitkeep
│   └── failed_transactions.csv      # 📊 synthetic dataset (600 transactions)
├── src/
│   ├── generate_data.py             # 🎭 Phase 1: synthetic data generator
│   ├── rules_engine.py              # 🎯 Phase 2: root cause + action selector
│   ├── train_model.py               # 🤖 Phase 3: ML stopping-rule model
│   └── messaging.py                 # 💬 Phase 4: cached LLM messaging
├── models/
│   ├── .gitkeep
│   └── stopping_model.pkl           # 🤖 trained model (gitignored)
├── app/
│   ├── __init__.py
│   ├── main.py                      # 🚪 FastAPI entry point, CORS setup
│   ├── pipeline.py                  # 📝 Phase 5: batch runner + audit log logic
│   └── routers/
│       ├── __init__.py
│       └── batch.py                 # 🔌 API endpoints (/run-batch, /report, /transactions)
├── frontend/
│   ├── index.html                   # 🖥️ dashboard UI
│   ├── style.css                    # 🎨 styling
│   └── script.js                    # ⚙️ fetch() calls to FastAPI backend
├── venv/                                   
├── requirements.txt                 # 📋 dependencies
├── .env.example                     # 🔑 env template
├── .env                             # 🔒 not committed
├── .gitignore                       # 🚫 gitignored
└── README.md
```

---

## 🚀 Running Locally

### ✅ Prerequisites
- 🐍 Python 3.10+
- 🔑 Anthropic API key (free tier credits work fine)

### 1️⃣ Clone the repository
```bash
git clone https://github.com/YOUR-USERNAME/RazorRecovery.git
cd RazorRecovery
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
Copy `.env.example` to `.env` and add your key:
```env
ANTHROPIC_API_KEY=your_key_here
```

### 5️⃣ Generate synthetic data
```bash
python src/generate_data.py
```

### 6️⃣ Train the ML stopping-rule model
```bash
python src/train_model.py
```

### 7️⃣ Run the batch pipeline
```bash
python src/run_batch.py
```

### 8️⃣ Launch the dashboard
```bash
streamlit run dashboard/app.py
```

---

## 🧠 Why This Design

Root-cause detection and action selection are kept **deterministic (rule-based)** because payment recovery needs consistency — an unpredictable LLM decision isn't acceptable when real money is involved.

The **ML model is used only for the stopping decision** — predicting whether a specific transaction pattern is worth retrying — because that's a genuine pattern-learning problem, not a fixed business rule.

The **LLM is used only for customer-facing messaging**, and cached per failure type (not called per transaction), keeping cost and latency minimal while still producing natural, human-friendly communication.

---

## 📊 Results

*(Fill in after running the full batch)*

| Metric | Value |
|---|---|
| Transactions processed | 600 |
| Recovery rate | *(pending Phase 5 batch run)* |
| Rupees recovered | *(pending Phase 5 batch run)* |
| Stopping-model precision / recall | 58% / 58% |

---

## ⚠️ Honest Limitations

- Execution is **simulated**, not connected to a real Razorpay test-mode API
- Dataset is **synthetic**, not real transaction history
- Stopping-rule model is trained on synthetic patterns and would need retraining on real data before production use
- The stopping-rule model is trained on synthetic data with hand-designed
  recovery patterns (65% accuracy, 58% precision/recall on held-out data).
  It should be read as a learned prior demonstrating case-specific
  decision-making, not a validated predictor — the architecture would
  need no changes to retrain on real transaction history.
- Early testing revealed the LLM would occasionally hallucinate actions (e.g., inventing a refund that wasn't part of the system's decision). We fixed this by explicitly grounding the prompt with the exact action chosen by the rule-based engine, preventing the LLM from inventing unauthorized actions — a real example of why deterministic decision-making + constrained LLM output is safer than LLM-driven decisions for financial systems.

---

## 🗺️ Roadmap

- [x] 1️⃣ Project setup + synthetic data generator 🎭
- [x] 2️⃣ Rule-based root cause + action engine 🎯
- [x] 3️⃣ ML stopping-rule model 🤖
- [x] 4️⃣ LLM messaging layer 💬
- [ ] 5️⃣ Audit log + batch runner 📝
- [ ] 6️⃣ Dashboard 📊
- [ ] 7️⃣ Documentation + polish 📚

**Progress: 1/7 phases complete**

---

## 👨‍💻 Author

**Chaitanya Sonawane**
- Built for Razorpay's AI Buildathon 2026 🚀