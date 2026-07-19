#!/usr/bin/env python3
"""
SupplySense Module 3: Stockout Prediction & Demand Spike Detection
Rule-based/statistical engine — no ML model needed for this signal.

This module:
1. Reads inventory.csv -> computes days-of-stock-remaining + stockout risk score/tier
2. Reads purchase_orders.csv -> compares recent 14-day order volume vs. prior baseline per product
3. Validates against known-injected ground truth (PROD0001-0008 stockout, PROD0051-0056 spikes)
4. Outputs stockout_risk.csv and demand_spikes.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings

warnings.filterwarnings("ignore")

# ============================================================================
# CONFIGURATION
# ============================================================================

DATA_DIR = Path("data")
OUTPUT_DIR = Path("data")

# Known-injected ground truth for validation
KNOWN_STOCKOUT_PRODUCTS = [f"PROD{i:04d}" for i in range(1, 9)]      # PROD0001-PROD0008
KNOWN_SPIKE_PRODUCTS = [f"PROD{i:04d}" for i in range(51, 57)]       # PROD0051-PROD0056

STOCKOUT_URGENCY_THRESHOLDS = {
    "Safe": (75, 101),
    "Watch": (50, 75),
    "Reorder Now": (25, 50),
    "Critical": (0, 25),
}

# Recent-vs-baseline window sizes (days)
RECENT_WINDOW_DAYS = 14
BASELINE_WINDOW_DAYS = 42  # 3x the recent window, immediately preceding it

# A product is flagged a demand spike if recent daily rate exceeds baseline by this much
SPIKE_THRESHOLD_PCT = 50.0


# ============================================================================
# DATA LOADING
# ============================================================================

def load_data():
    print("Loading data files...")
    inventory = pd.read_csv(DATA_DIR / "inventory.csv")
    purchase_orders = pd.read_csv(DATA_DIR / "purchase_orders.csv")

    print(f"  - Loaded {len(inventory)} inventory records")
    print(f"  - Loaded {len(purchase_orders)} purchase orders")

    return inventory, purchase_orders


# ============================================================================
# STOCKOUT RISK
# ============================================================================

def compute_stockout_risk(inventory):
    """
    days_of_stock_remaining = current_stock / avg_daily_demand
    stockout_risk_score (0-100, higher = more urgent) blends:
      - stock coverage relative to reorder_threshold (how far below/above the reorder line)
      - days_of_stock_remaining (how soon it runs out in absolute terms)
    """
    print("\nComputing stockout risk...")
    df = inventory.copy()

    # Guard against div-by-zero (no product in this dataset has 0 demand, but be safe)
    safe_demand = df["avg_daily_demand"].replace(0, np.nan)
    df["days_of_stock_remaining"] = (df["current_stock"] / safe_demand).round(1)
    df["days_of_stock_remaining"] = df["days_of_stock_remaining"].fillna(df["current_stock"])

    # Signal 1: stock position relative to reorder threshold.
    # ratio < 1 means already below the reorder line (urgent); > 1 means comfortably above it.
    stock_to_threshold_ratio = df["current_stock"] / df["reorder_threshold"].replace(0, np.nan)
    stock_to_threshold_ratio = stock_to_threshold_ratio.fillna(stock_to_threshold_ratio.median())
    # Map ratio to a 0-100 urgency component: ratio 0 -> 100, ratio 1 (at threshold) -> 50,
    # ratio >= 2 -> 0. Clipped and linear in between.
    threshold_component = (100 - (stock_to_threshold_ratio * 50)).clip(lower=0, upper=100)

    # Signal 2: absolute days of stock remaining. <=7 days -> max urgency, >=60 days -> none.
    days_component = (100 - (df["days_of_stock_remaining"] / 60 * 100)).clip(lower=0, upper=100)

    # Blend: threshold position is the primary signal, days-remaining refines it
    df["stockout_risk_score"] = (0.55 * threshold_component + 0.45 * days_component).round(1)

    def assign_tier(score):
        for tier, (low, high) in STOCKOUT_URGENCY_THRESHOLDS.items():
            if low <= score < high:
                return tier
        return "Critical"  # score == 100 edge case

    # Higher score = more urgent, so invert the lookup (thresholds above are defined low->high
    # score bands per tier name, but tier urgency increases as score increases)
    df["stockout_urgency"] = df["stockout_risk_score"].apply(
        lambda s: "Critical" if s >= 75 else "Reorder Now" if s >= 50 else "Watch" if s >= 25 else "Safe"
    )

    return df


# ============================================================================
# DEMAND SPIKE DETECTION
# ============================================================================

def compute_demand_spikes(purchase_orders):
    """
    Compare each product's order quantity in the most recent RECENT_WINDOW_DAYS
    against its average daily rate over the preceding BASELINE_WINDOW_DAYS,
    scaled to the same window length so the comparison is apples-to-apples.

    "Most recent" is anchored to the latest order_date in the dataset (this is
    historical synthetic data, not a live feed).
    """
    print("\nComputing demand spikes...")
    df = purchase_orders.copy()
    df["order_date"] = pd.to_datetime(df["order_date"])

    latest_date = df["order_date"].max()
    recent_start = latest_date - pd.Timedelta(days=RECENT_WINDOW_DAYS - 1)
    baseline_start = recent_start - pd.Timedelta(days=BASELINE_WINDOW_DAYS)
    baseline_end = recent_start - pd.Timedelta(days=1)

    recent = df[(df["order_date"] >= recent_start) & (df["order_date"] <= latest_date)]
    baseline = df[(df["order_date"] >= baseline_start) & (df["order_date"] <= baseline_end)]

    recent_qty = recent.groupby("product_id")["quantity_ordered"].sum()
    baseline_qty_total = baseline.groupby("product_id")["quantity_ordered"].sum()

    # Scale baseline total down to the same window length as "recent" for a fair comparison
    baseline_qty_scaled = (baseline_qty_total / BASELINE_WINDOW_DAYS * RECENT_WINDOW_DAYS).round(1)

    all_products = sorted(set(recent_qty.index) | set(baseline_qty_scaled.index))
    result = pd.DataFrame({"product_id": all_products})
    result["recent_14day_qty"] = result["product_id"].map(recent_qty).fillna(0).astype(int)
    result["historical_avg_qty"] = result["product_id"].map(baseline_qty_scaled).fillna(0)

    def pct_increase(row):
        if row["historical_avg_qty"] <= 0:
            # No baseline orders at all: treat any recent orders as a spike signal
            return 999.0 if row["recent_14day_qty"] > 0 else 0.0
        return round(
            (row["recent_14day_qty"] - row["historical_avg_qty"]) / row["historical_avg_qty"] * 100, 1
        )

    result["pct_increase"] = result.apply(pct_increase, axis=1)
    result["is_spike"] = result["pct_increase"] >= SPIKE_THRESHOLD_PCT

    return result


# ============================================================================
# OUTPUT
# ============================================================================

def generate_outputs(inventory, stockout_df, product_names, demand_df):
    stockout_out = stockout_df[[
        "product_id", "product_name", "warehouse_id", "current_stock",
        "reorder_threshold", "avg_daily_demand", "days_of_stock_remaining",
        "stockout_risk_score", "stockout_urgency"
    ]].sort_values("stockout_risk_score", ascending=False)

    demand_out = demand_df.copy()
    demand_out["product_name"] = demand_out["product_id"].map(product_names)
    demand_out = demand_out[[
        "product_id", "product_name", "recent_14day_qty",
        "historical_avg_qty", "pct_increase", "is_spike"
    ]].sort_values("pct_increase", ascending=False)

    stockout_out.to_csv(OUTPUT_DIR / "stockout_risk.csv", index=False)
    demand_out.to_csv(OUTPUT_DIR / "demand_spikes.csv", index=False)

    return stockout_out, demand_out


# ============================================================================
# VALIDATION
# ============================================================================

def validate_ground_truth(stockout_out, demand_out):
    print("\n" + "=" * 80)
    print("GROUND TRUTH VALIDATION")
    print("=" * 80)

    issues = []

    # Stockout ground truth: PROD0001-0008 should land in Reorder Now / Critical
    stockout_lookup = stockout_out.set_index("product_id")["stockout_urgency"]
    print("\nStockout check (expect Reorder Now / Critical):")
    for pid in KNOWN_STOCKOUT_PRODUCTS:
        if pid not in stockout_lookup.index:
            issues.append(f"{pid} not found in inventory.csv")
            print(f"  {pid}: NOT FOUND")
            continue
        tier = stockout_lookup[pid]
        ok = tier in ("Reorder Now", "Critical")
        print(f"  {pid}: {tier} {'[OK]' if ok else '[MISS]'}")
        if not ok:
            issues.append(f"{pid} landed in '{tier}', expected Reorder Now/Critical")

    # Spike ground truth: PROD0051-0056 should be flagged is_spike == True
    spike_lookup = demand_out.set_index("product_id")["is_spike"]
    pct_lookup = demand_out.set_index("product_id")["pct_increase"]
    print("\nDemand spike check (expect is_spike = True):")
    for pid in KNOWN_SPIKE_PRODUCTS:
        if pid not in spike_lookup.index:
            issues.append(f"{pid} not found in purchase_orders.csv")
            print(f"  {pid}: NOT FOUND")
            continue
        flagged = bool(spike_lookup[pid])
        pct = pct_lookup[pid]
        print(f"  {pid}: pct_increase={pct}% is_spike={flagged} {'[OK]' if flagged else '[MISS]'}")
        if not flagged:
            issues.append(f"{pid} not flagged as spike (pct_increase={pct}%)")

    print("\n" + "-" * 80)
    if issues:
        print(f"[ISSUES FOUND] {len(issues)} validation issue(s):")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("[OK] All known-injected products validated correctly")
    print("=" * 80)

    return len(issues) == 0, issues


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("\n" + "=" * 80)
    print("SUPPLYSENSE MODULE 3: STOCKOUT PREDICTION & DEMAND SPIKE DETECTION")
    print("=" * 80)

    inventory, purchase_orders = load_data()

    stockout_df = compute_stockout_risk(inventory)
    demand_df = compute_demand_spikes(purchase_orders)

    product_names = inventory.set_index("product_id")["product_name"]
    stockout_out, demand_out = generate_outputs(inventory, stockout_df, product_names, demand_df)

    passed, issues = validate_ground_truth(stockout_out, demand_out)

    n_critical = (stockout_out["stockout_urgency"] == "Critical").sum()
    n_reorder = (stockout_out["stockout_urgency"] == "Reorder Now").sum()
    n_spikes = int(demand_out["is_spike"].sum())

    print("\n" + "=" * 80)
    print("DEMAND ENGINE EXECUTION COMPLETE")
    print("=" * 80)
    print(f"\nOutputs: {OUTPUT_DIR / 'stockout_risk.csv'}, {OUTPUT_DIR / 'demand_spikes.csv'}")
    print(f"Products scored: {len(stockout_out)} | Critical: {n_critical} | Reorder Now: {n_reorder}")
    print(f"Demand spikes flagged: {n_spikes}")
    print(f"Validation status: {'PASSED' if passed else 'ISSUES FOUND'}")
    print()

    return stockout_out, demand_out, passed, issues


if __name__ == "__main__":
    main()
