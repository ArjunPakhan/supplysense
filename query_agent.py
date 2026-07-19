#!/usr/bin/env python3
"""
SupplySense Module 4: Natural Language Query Agent
LLM function-calling agent that reasons over Module 2/3 outputs to answer
supply chain questions. This is the agentic centerpiece of the project —
the model decides which tools to call and grounds every answer in real data.

Uses Groq (Llama 3.3 70B, OpenAI-compatible tool-calling API).
"""

import os
import json
from pathlib import Path

import pandas as pd
from groq import Groq

warnings_shown = False

# ============================================================================
# CONFIGURATION
# ============================================================================

DATA_DIR = Path("data")
MODEL = "llama-3.3-70b-versatile"
MAX_TOOL_ROUNDS = 5


def load_env_file():
    """Minimal .env loader so GROQ_API_KEY doesn't need to be exported per shell."""
    env_path = Path(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


load_env_file()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


# ============================================================================
# DATA LOADING (cached at module load — this is a demo-scale dataset)
# ============================================================================

def load_all_data():
    return {
        "suppliers": pd.read_csv(DATA_DIR / "suppliers.csv"),
        "supplier_risk_scores": pd.read_csv(DATA_DIR / "supplier_risk_scores.csv"),
        "stockout_risk": pd.read_csv(DATA_DIR / "stockout_risk.csv"),
        "demand_spikes": pd.read_csv(DATA_DIR / "demand_spikes.csv"),
        "purchase_orders": pd.read_csv(DATA_DIR / "purchase_orders.csv"),
        "shipments": pd.read_csv(DATA_DIR / "shipments.csv"),
        "inventory": pd.read_csv(DATA_DIR / "inventory.csv"),
    }


DATA = load_all_data()


# ============================================================================
# TOOL IMPLEMENTATIONS
# Each returns a small JSON-serializable dict/list — never a full CSV dump.
# ============================================================================

def get_high_risk_suppliers(tier=None, top_n=10):
    """Suppliers from supplier_risk_scores.csv, optionally filtered by risk_tier,
    sorted by hybrid_risk_score descending (most at-risk first)."""
    df = DATA["supplier_risk_scores"].copy()
    if tier:
        df = df[df["risk_tier"].str.lower() == tier.lower()]
    df = df.sort_values("hybrid_risk_score", ascending=False).head(top_n)
    return df[[
        "supplier_id", "supplier_name", "risk_tier", "hybrid_risk_score",
        "on_time_delivery_rate", "avg_delay_days", "cancellation_rate"
    ]].to_dict(orient="records")


def get_stockout_risks(urgency=None, top_n=15):
    """Products from stockout_risk.csv, optionally filtered by stockout_urgency,
    sorted by stockout_risk_score descending (most urgent first)."""
    df = DATA["stockout_risk"].copy()
    if urgency:
        df = df[df["stockout_urgency"].str.lower() == urgency.lower()]
    df = df.sort_values("stockout_risk_score", ascending=False).head(top_n)
    return df.to_dict(orient="records")


def get_demand_spikes(only_spikes=True, top_n=15):
    """Products from demand_spikes.csv, sorted by pct_increase descending."""
    df = DATA["demand_spikes"].copy()
    if only_spikes:
        df = df[df["is_spike"] == True]  # noqa: E712
    df = df.sort_values("pct_increase", ascending=False).head(top_n)
    return df.to_dict(orient="records")


def get_supplier_delivery_history(supplier_id, limit=10):
    """Recent PO + shipment history for one supplier, plus its risk score."""
    po = DATA["purchase_orders"]
    ship = DATA["shipments"]
    risk = DATA["supplier_risk_scores"]

    supplier_pos = po[po["supplier_id"] == supplier_id].copy()
    if supplier_pos.empty:
        return {"error": f"No purchase orders found for supplier_id '{supplier_id}'"}

    merged = supplier_pos.merge(ship, on="po_id", how="left", suffixes=("_po", "_shipment"))
    merged = merged.sort_values("order_date", ascending=False).head(limit)

    risk_row = risk[risk["supplier_id"] == supplier_id]
    risk_summary = risk_row.to_dict(orient="records")[0] if not risk_row.empty else None

    return {
        "risk_summary": risk_summary,
        "recent_orders": merged[[
            "po_id", "product_id", "order_date", "promised_delivery_date",
            "actual_delivery_date", "status_po", "delay_reason"
        ]].to_dict(orient="records"),
    }


def get_product_details(product_id):
    """Inventory + stockout risk info for one product, including which
    single warehouse currently stocks it in this dataset."""
    inv = DATA["inventory"]
    stockout = DATA["stockout_risk"]

    inv_row = inv[inv["product_id"] == product_id]
    if inv_row.empty:
        return {"error": f"No inventory record found for product_id '{product_id}'"}

    stockout_row = stockout[stockout["product_id"] == product_id]

    return {
        "inventory": inv_row.to_dict(orient="records")[0],
        "stockout_risk": stockout_row.to_dict(orient="records")[0] if not stockout_row.empty else None,
        "note": "In this dataset each product is stocked at exactly one warehouse "
                "(single-warehouse-per-SKU model, multi-warehouse allocation is out of v1 scope).",
    }


TOOL_FUNCTIONS = {
    "get_high_risk_suppliers": get_high_risk_suppliers,
    "get_stockout_risks": get_stockout_risks,
    "get_demand_spikes": get_demand_spikes,
    "get_supplier_delivery_history": get_supplier_delivery_history,
    "get_product_details": get_product_details,
}


# ============================================================================
# TOOL SCHEMAS (OpenAI-compatible function-calling format, used by Groq)
# ============================================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_high_risk_suppliers",
            "description": "Get suppliers from the risk engine, ranked by hybrid_risk_score "
                            "(0-100, higher = more likely to miss deliveries / cause disruption). "
                            "Use this to answer questions about which suppliers are risky, "
                            "unreliable, or likely to miss deliveries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tier": {
                        "type": "string",
                        "enum": ["Low", "Medium", "High", "Critical"],
                        "description": "Optional filter by risk tier. Omit to get all suppliers ranked."
                    },
                    "top_n": {"type": "integer", "description": "Max results to return. Default 10."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_stockout_risks",
            "description": "Get products from the stockout prediction engine, ranked by "
                            "stockout_risk_score (0-100, higher = more urgent). Use this to answer "
                            "questions about which products are low on stock or at risk of running out.",
            "parameters": {
                "type": "object",
                "properties": {
                    "urgency": {
                        "type": "string",
                        "enum": ["Safe", "Watch", "Reorder Now", "Critical"],
                        "description": "Optional filter by stockout_urgency tier. Omit to get all, ranked."
                    },
                    "top_n": {"type": "integer", "description": "Max results to return. Default 15."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_demand_spikes",
            "description": "Get products with abnormal recent demand spikes (recent 14-day order "
                            "volume vs. historical baseline). Use this for questions about unusual "
                            "demand, promotions-driven surges, or what's causing sudden disruption.",
            "parameters": {
                "type": "object",
                "properties": {
                    "only_spikes": {
                        "type": "boolean",
                        "description": "If true (default), only return products flagged is_spike=True."
                    },
                    "top_n": {"type": "integer", "description": "Max results to return. Default 15."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_supplier_delivery_history",
            "description": "Get a specific supplier's risk score plus their recent purchase order "
                            "and shipment history (delivery dates, delays, cancellations). Use this "
                            "to explain WHY a specific supplier is risky or to root-cause a disruption.",
            "parameters": {
                "type": "object",
                "properties": {
                    "supplier_id": {"type": "string", "description": "e.g. 'SUP001'"},
                    "limit": {"type": "integer", "description": "Max recent orders to return. Default 10."}
                },
                "required": ["supplier_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_details",
            "description": "Get full inventory + stockout risk detail for one specific product, "
                            "including which warehouse stocks it and current stock level. Use this "
                            "for questions about a specific product or fulfilling an order for it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "e.g. 'PROD0003'"}
                },
                "required": ["product_id"]
            }
        }
    },
]

SYSTEM_PROMPT = """You are SupplySense, an AI supply chain risk analyst. You answer questions \
about supplier reliability, inventory stockout risk, and demand anomalies by calling tools that \
query the company's real risk-engine outputs. Never guess or fabricate numbers — always call a \
tool to get grounded data before answering. When you have enough information, give a concise, \
decision-useful answer citing specific supplier IDs, product IDs, and scores. If asked about \
"today's biggest disruption", check both high-risk suppliers and stockout/demand-spike signals, \
then reason about which single issue has the largest business impact and explain why."""


# ============================================================================
# AGENT LOOP
# ============================================================================

def ask(question, verbose=True):
    """Run the tool-calling loop for one question. Returns (final_answer, trail)."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    trail = []

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.2,
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content, trail

        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
        })

        for tc in msg.tool_calls:
            fn_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                args = {}

            fn = TOOL_FUNCTIONS.get(fn_name)
            result = fn(**args) if fn else {"error": f"Unknown tool '{fn_name}'"}

            trail.append({"tool": fn_name, "args": args, "result_preview": result})
            if verbose:
                print(f"  [tool call] {fn_name}({args})")

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, default=str),
            })

    return "Reached max tool-call rounds without a final answer.", trail


# ============================================================================
# TEST RUNNER — the 4 sample questions from the problem statement
# ============================================================================

TEST_QUESTIONS = [
    "Which suppliers are most likely to miss deliveries next week?",
    "Which products are at risk of going out of stock?",
    "What is causing today's biggest supply chain disruption?",
    "We need to fulfill an order for 50 units of PROD0003. Which warehouse should fulfill this order?",
]


def run_test_questions():
    print("\n" + "=" * 80)
    print("SUPPLYSENSE MODULE 4: NATURAL LANGUAGE QUERY AGENT - TEST RUN")
    print("=" * 80)

    for i, q in enumerate(TEST_QUESTIONS, 1):
        print(f"\n{'-' * 80}\nQ{i}: {q}\n{'-' * 80}")
        answer, trail = ask(q)
        print(f"\nANSWER:\n{answer}\n")

    print("=" * 80)
    print("TEST RUN COMPLETE - all 4 problem-statement questions answered above")
    print("=" * 80)


def interactive_loop():
    print("SupplySense NL Query Agent - type a question, or 'quit' to exit.")
    while True:
        try:
            q = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q or q.lower() in ("quit", "exit"):
            break
        answer, _ = ask(q)
        print(f"\n{answer}")


if __name__ == "__main__":
    import sys
    if "--interactive" in sys.argv:
        interactive_loop()
    else:
        run_test_questions()
