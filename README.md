# SupplySense

**AI-powered supply chain risk and inventory intelligence agent**

## Problem

Businesses typically monitor their supply chains through disconnected dashboards, spreadsheets, ERPs, and email threads. As a result, disruptions — delayed shipments, unreliable suppliers, demand spikes — are usually discovered only after they've already impacted customers. SupplySense is an operational decision-support agent that continuously scores risk and answers plain-English questions, so problems can be anticipated instead of reacted to.

## Live Demo

**[supplysense-hackathon.streamlit.app](https://supplysense-hackathon.streamlit.app/)**

## What It Does

- **Supplier risk scoring** — hybrid rule-based + Isolation Forest anomaly detection, blended into a single 0–100 risk score per supplier
- **Stockout & demand spike prediction** — rule-based/statistical engine flagging products at risk of running out and abnormal recent demand
- **Natural language query agent** — Groq-powered (Llama 3.3 70B) tool-calling loop that answers questions grounded in real data, with a visible reasoning trail
- **Executive summary generation** — AI-written operations briefing ranking the top issues across all risk sources
- **Live dashboard** — single-page Streamlit app tying all of the above together

## Architecture

| File | Module |
|---|---|
| `data_generator.py` | Generates the synthetic dataset (suppliers, shipments, inventory, purchase orders) with seeded, injected anomalies |
| `risk_engine.py` | Computes supplier reliability scores via a hybrid rule-based + Isolation Forest engine |
| `demand_engine.py` | Predicts stockout risk and detects demand spikes from inventory and purchase order data |
| `query_agent.py` | LLM tool-calling agent that answers natural language questions grounded in the engine outputs |
| `dashboard.py` | Single-page Streamlit dashboard tying together risk tables, alerts, the query agent, and the executive summary |
| `exec_summary.py` | One-shot LLM call that generates a plain-text executive briefing from the top-ranked risk issues |

## Tech Stack

- **Python** with **pandas** for data processing
- **scikit-learn** (Isolation Forest) for anomaly detection
- **Groq** (Llama 3.3 70B) for LLM function-calling and summary generation
- **Streamlit** for the dashboard

## How to Run Locally

```bash
git clone https://github.com/ArjunPakhan/supplysense.git
cd supplysense
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file in the project root:

```
GROQ_API_KEY=your_key_here
```

Run each module in order to build the dataset and risk outputs, then launch the dashboard:

```bash
python data_generator.py
python risk_engine.py
python demand_engine.py
streamlit run dashboard.py
```

## Validation Notes

Ground-truth anomalies are deliberately injected into the synthetic dataset (chronically late suppliers, declining-quality suppliers, products trending toward stockout, products with demand spikes), and each engine validates its output against these known cases rather than assuming correctness.

One honest known limitation: supplier **SUP008** is injected as a "declining quality" supplier but scores **Medium** risk rather than High/Critical. Investigation confirmed this isn't a bug — SUP008 has a genuinely strong on-time delivery rate (84.6%) and low delay (1.0 day); its issue is a high cancellation rate (21.9%), which the model correctly reads as a milder, commercially-driven problem rather than an operational failure. Rather than tuning the scoring weights to force a match against the label, this is documented as a real edge case in how the model reasons about supplier risk — the score doesn't overreact to a single high-cancellation supplier that's otherwise reliable.

## Built For

Agentic AI Hackathon, hosted by Product Space in collaboration with Code Benders.
