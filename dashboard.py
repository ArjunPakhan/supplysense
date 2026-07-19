#!/usr/bin/env python3
"""
SupplySense Module 5: Minimal Single-Page Dashboard
Three sections: supplier risk table, stockout/demand alerts, NL query box.
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

st.write(st.session_state.exec_summary)

if st.button("Regenerate"):
    with st.spinner("Generating executive summary..."):
        st.session_state.exec_summary = generate_executive_summary()
    st.rerun()

# ============================================================================
# SECTION 1: SUPPLIER RISK
# ============================================================================

st.header("1. Supplier Risk")

supplier_risk = load_csv("supplier_risk_scores.csv").sort_values(
    "hybrid_risk_score", ascending=False
)

st.dataframe(
    supplier_risk[[
        "supplier_id", "supplier_name", "risk_tier", "hybrid_risk_score",
        "on_time_delivery_rate", "avg_delay_days", "cancellation_rate"
    ]].style.map(color_tier, subset=["risk_tier"]),
    width='stretch',
    hide_index=True,
)

# ============================================================================
# SECTION 2: STOCKOUT & DEMAND ALERTS
# ============================================================================

st.header("2. Stockout & Demand Alerts")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Stockout Risk (Reorder Now / Critical)")
    stockout = load_csv("stockout_risk.csv")
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
    demand = load_csv("demand_spikes.csv")
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
    st.write(answer)

    with st.expander(f"Reasoning trail ({len(trail)} tool call(s))"):
        if not trail:
            st.write("No tool calls were made for this answer.")
        for i, step in enumerate(trail, 1):
            st.markdown(f"**{i}. `{step['tool']}({step['args']})`**")
            st.json(step["result_preview"])
