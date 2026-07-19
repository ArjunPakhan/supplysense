#!/usr/bin/env python3
"""
SupplySense Module 6: AI-Generated Executive Summary
Ranks the top 3 most urgent issues across supplier risk, stockout risk, and
demand spikes, then sends them to Groq for a one-shot (non-agentic) summary.
This is a single prompt -> single response call, deliberately kept separate
from query_agent.py's tool-calling loop.
"""

import pandas as pd
from groq import Groq

from query_agent import DATA_DIR, MODEL, load_env_file

load_env_file()

import os  # noqa: E402  (after load_env_file so GROQ_API_KEY is set)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Demand-spike pct_increase has no natural 0-100 ceiling, so it's capped here
# to make it comparable to the risk-engine scores (which are already 0-100).
SPIKE_SEVERITY_CAP = 100
SPIKE_SEVERITY_DIVISOR = 10  # pct_increase / 10, capped at 100


def _top_supplier_issues():
    df = pd.read_csv(DATA_DIR / "supplier_risk_scores.csv")
    df = df.sort_values("hybrid_risk_score", ascending=False)
    issues = []
    for _, row in df.iterrows():
        issues.append({
            "category": "Supplier Risk",
            "id": row["supplier_id"],
            "name": row["supplier_name"],
            "severity_score": round(float(row["hybrid_risk_score"]), 1),
            "detail": (
                f"risk_tier={row['risk_tier']}, "
                f"on_time_delivery_rate={row['on_time_delivery_rate']:.1f}%, "
                f"avg_delay_days={row['avg_delay_days']:.1f}, "
                f"cancellation_rate={row['cancellation_rate']:.1f}%"
            ),
        })
    return issues


def _top_stockout_issues():
    df = pd.read_csv(DATA_DIR / "stockout_risk.csv")
    df = df.sort_values("stockout_risk_score", ascending=False)
    issues = []
    for _, row in df.iterrows():
        issues.append({
            "category": "Stockout Risk",
            "id": row["product_id"],
            "name": row["product_name"],
            "severity_score": round(float(row["stockout_risk_score"]), 1),
            "detail": (
                f"urgency={row['stockout_urgency']}, "
                f"warehouse={row['warehouse_id']}, "
                f"current_stock={row['current_stock']}, "
                f"days_of_stock_remaining={row['days_of_stock_remaining']}"
            ),
        })
    return issues


def _top_demand_spike_issues():
    df = pd.read_csv(DATA_DIR / "demand_spikes.csv")
    df = df[df["is_spike"] == True]  # noqa: E712
    issues = []
    for _, row in df.iterrows():
        severity = min(SPIKE_SEVERITY_CAP, row["pct_increase"] / SPIKE_SEVERITY_DIVISOR)
        issues.append({
            "category": "Demand Spike",
            "id": row["product_id"],
            "name": row["product_name"],
            "severity_score": round(float(severity), 1),
            "detail": (
                f"recent_14day_qty={row['recent_14day_qty']}, "
                f"historical_avg_qty={row['historical_avg_qty']}, "
                f"pct_increase={row['pct_increase']:.1f}%"
            ),
        })
    return issues


def get_top_issues(n=3):
    """Combine all three sources into one ranked list by severity_score, take top n."""
    all_issues = _top_supplier_issues() + _top_stockout_issues() + _top_demand_spike_issues()
    all_issues.sort(key=lambda x: x["severity_score"], reverse=True)
    return all_issues[:n]


SUMMARY_PROMPT_TEMPLATE = """You are writing a supply chain operations briefing for an executive \
audience. Here are the top {n} most urgent issues right now, ranked by severity (0-100 scale, \
higher = more urgent), pulled directly from the risk engine outputs:

{issues_text}

Write a concise executive summary (150-200 words) in the voice of an operations briefing. Cover:
- What is happening (cite the specific supplier/product IDs and scores above)
- Why it matters for the business
- 1-2 concrete recommended actions

Do not invent any numbers or entities beyond what's listed above. Plain text only, no headers \
or bullet points — a flowing briefing paragraph or two."""


def _format_issues(issues):
    lines = []
    for i, issue in enumerate(issues, 1):
        lines.append(
            f"{i}. [{issue['category']}] {issue['id']} ({issue['name']}) - "
            f"severity {issue['severity_score']}/100 - {issue['detail']}"
        )
    return "\n".join(lines)


def generate_executive_summary(n=3):
    """Pull top-n issues across all sources and generate a plain-text exec summary via Groq."""
    issues = get_top_issues(n)
    prompt = SUMMARY_PROMPT_TEMPLATE.format(n=n, issues_text=_format_issues(issues))

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=400,
    )
    return response.choices[0].message.content.strip()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("SUPPLYSENSE MODULE 6: EXECUTIVE SUMMARY - TEST RUN")
    print("=" * 80)

    top = get_top_issues(3)
    print("\nTop 3 issues feeding the summary:")
    print(_format_issues(top))

    print("\n" + "-" * 80)
    print("GENERATED SUMMARY:")
    print("-" * 80)
    print(generate_executive_summary())
    print()
