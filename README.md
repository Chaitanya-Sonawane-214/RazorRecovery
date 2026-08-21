# RazorRecovery

*An independent project built for Razorpay's AI Buildathon 2026 — Track 3: AI Revenue Recovery*

## Problem statement

[1-2 paragraphs: what revenue loss looks like — payments fail for preventable
reasons, and most systems just log the failure instead of acting on it.
State the specific slice you're tackling: payment degradation → root cause →
recovery action.]

## What this does

[2-3 sentences: detects why a payment failed, decides the right recovery
action, uses a small ML model to decide whether retrying is worth it, and
logs every decision — then reports how much money was recovered across a
batch.]

## Architecture

[Insert architecture diagram image here]

Pipeline: failed payment → rule-based root cause detection → rule-based
action selector → ML-powered recovery-probability model (stop or continue)
→ cached LLM message generation → audit log → batch report.

## Why this design

[Short paragraph explaining the reasoning: root cause and action selection
are deterministic because payment recovery needs consistency; the ML model
decides stopping, since that's a genuine pattern-learning problem; LLM is
used only for natural-language messaging, and cached per failure type to
keep cost and latency low.]

## Tech stack

- Python
- pandas, scikit-learn (ML model)
- [Flask / Streamlit] (dashboard)
- Anthropic/OpenAI API (customer messaging only)
- Faker (synthetic data generation)

## Setup and run

```bash
git clone <repo-url>
cd razor-recovery
pip install -r requirements.txt

# 1. Generate synthetic data
python src/generate_data.py

# 2. Train the ML stopping-rule model
python src/train_model.py

# 3. Run the batch pipeline
python src/run_batch.py

# 4. Launch dashboard
streamlit run dashboard/app.py
```

## Results

[Fill in after running the batch: total transactions processed, recovery
rate %, total rupees recovered, model precision/recall.]

| Metric | Value |
|---|---|
| Transactions processed | |
| Recovery rate | |
| Rupees recovered | |
| Model precision / recall | |

## Honest limitations

[What this doesn't do yet — e.g. execution is simulated, not connected to
a real payment gateway; synthetic data, not real transaction history;
stopping-rule model trained on synthetic patterns, would need retraining
on real data.]

## What I'd build next

[1-2 lines: real Razorpay test-mode API integration, more failure
categories, live retry scheduling, etc.]