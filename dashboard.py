#!/usr/bin/env python3
"""
SupplySense Module 5: Minimal Single-Page Dashboard
Four sections: executive summary, supplier risk table, stockout/demand
alerts, NL query box.
Run with: streamlit run dashboard.py
"""

import pandas as pd
import streamlit as st

from query_agent import ask
from exec_summary import generate_executive_summary

DATA_DIR = "data"

st.set_page_config(page_title="SupplySense", layout="wide")

TIER_COLORS = {
    "Critical": "#ff4b4b",
    "High": "#ffa64b",
    "Medium": "#ffe14b",
    "Low": "#4bd671",
}


def color_tier(val):
    color = TIER_COLORS.get(val, "")
    if not color:
        return ""
    return f"background-color: {color}; color: #111;"


@st.cache_data
def load_csv(name):
    return pd.read_csv(f"{DATA_DIR}/{name}")


st.title("SupplySense")
st.caption("AI Supply Chain Risk & Inventory Intelligence")

# ============================================================================
# SECTION 0: EXECUTIVE SUMMARY
# ============================================================================

st.header("Executive Summary")

if "exec_summary" not in st.session_state:
    with st.spinner("Generating executive summary..."):
        st.session_state.exec_summary = generate_executive_summary()

with st.container(border=True):
    st.write(st.session_state.exec_summary)

if st.button("Regenerate"):
    with st.spinner("Generating executive summary..."):
        st.session_state.exec_summary = generate_executive_summary()
    st.rerun()

st.divider()

# ============================================================================
# SECTION 1: SUPPLIER RISK
# ============================================================================

st.header("1. Supplier Risk")

supplier_risk = load_csv("supplier_risk_scores.csv").sort_values(
    "hybrid_risk_score", ascending=False
)

tier_counts = supplier_risk["risk_tier"].value_counts()
m1, m2, m3, m4 = st.columns(4)
m1.metric("🔴 Critical", int(tier_counts.get("Critical", 0)))
m2.metric("🟠 High", int(tier_counts.get("High", 0)))
m3.metric("🟡 Medium", int(tier_counts.get("Medium", 0)))
m4.metric("🟢 Low", int(tier_counts.get("Low", 0)))

st.dataframe(
    supplier_risk[[
        "supplier_id", "supplier_name", "risk_tier", "hybrid_risk_score",
        "on_time_delivery_rate", "avg_delay_days", "cancellation_rate"
    ]].style.map(color_tier, subset=["risk_tier"]),
    width='stretch',
    hide_index=True,
)

st.divider()

# ============================================================================
# SECTION 2: STOCKOUT & DEMAND ALERTS
# ============================================================================

st.header("2. Stockout & Demand Alerts")

stockout = load_csv("stockout_risk.csv")
demand = load_csv("demand_spikes.csv")

urgency_counts = stockout["stockout_urgency"].value_counts()
spike_count = int((demand["is_spike"] == True).sum())  # noqa: E712

s1, s2, s3, s4 = st.columns(4)
s1.metric("🔴 Critical Stockouts", int(urgency_counts.get("Critical", 0)))
s2.metric("🟠 Reorder Now", int(urgency_counts.get("Reorder Now", 0)))
s3.metric("🟡 Watch", int(urgency_counts.get("Watch", 0)))
s4.metric("📈 Demand Spikes", spike_count)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Stockout Risk (Reorder Now / Critical)")
    urgent = stockout[stockout["stockout_urgency"].isin(["Reorder Now", "Critical"])].sort_values(
        "stockout_risk_score", ascending=False
    )
    if urgent.empty:
        st.info("No products currently in Reorder Now / Critical tiers.")
    else:
        st.dataframe(
            urgent[[
                "product_id", "product_name", "warehouse_id", "current_stock",
                "days_of_stock_remaining", "stockout_risk_score", "stockout_urgency"
            ]].style.map(color_tier, subset=["stockout_urgency"]),
            width='stretch',
            hide_index=True,
        )

with col2:
    st.subheader("Demand Spikes")
    spikes = demand[demand["is_spike"] == True].sort_values(  # noqa: E712
        "pct_increase", ascending=False
    )
    if spikes.empty:
        st.info("No demand spikes flagged.")
    else:
        st.dataframe(
            spikes[["product_id", "product_name", "recent_14day_qty",
                    "historical_avg_qty", "pct_increase"]],
            width='stretch',
            hide_index=True,
        )

st.divider()

# ============================================================================
# SECTION 3: ASK SUPPLYSENSE
# ============================================================================

st.header("3. Ask SupplySense")

question = st.text_input(
    "Ask a question about supplier risk, stockouts, or disruptions",
    placeholder="e.g. Which suppliers are most likely to miss deliveries next week?",
)

if st.button("Ask", type="primary") and question.strip():
    with st.spinner("Reasoning over live risk data..."):
        answer, trail = ask(question, verbose=False)

    st.markdown("**Answer:**")
    with st.container(border=True):
        st.write(answer)

    with st.expander(f"🔍 Reasoning trail ({len(trail)} tool call(s))"):
        if not trail:
            st.write("No tool calls were made for this answer.")
        for i, step in enumerate(trail, 1):
            st.markdown(f"**{i}. `{step['tool']}({step['args']})`**")
            st.json(step["result_preview"])
