#!/usr/bin/env python3
"""
SupplySense Module 2: Supplier Risk Engine
Computes a hybrid Supplier Risk Score (0-100) using rule-based features + ML anomaly detection.

This module:
1. Reads suppliers.csv, purchase_orders.csv, shipments.csv
2. Computes rule-based features per supplier (on-time rate, delays, cancellation, etc.)
3. Applies Isolation Forest for anomaly detection
4. Blends rule-based + ML scores into a hybrid risk score
5. Assigns risk tiers and outputs supplier_risk_scores.csv
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import IsolationForest
from pathlib import Path
import warnings

warnings.filterwarnings("ignore")

# ============================================================================
# CONFIGURATION
# ============================================================================

DATA_DIR = Path("data")
OUTPUT_DIR = Path("data")

# Known-bad suppliers for validation
KNOWN_BAD_SUPPLIERS = [
    "SUP001", "SUP002", "SUP003", "SUP004", "SUP005",  # chronic lateness
    "SUP006", "SUP007", "SUP008"                        # declining quality
]

# Risk tier thresholds
RISK_TIER_THRESHOLDS = {
    "Low": (0, 25),
    "Medium": (25, 50),
    "High": (50, 75),
    "Critical": (75, 101)
}

# Weights for rule-based component
RULE_WEIGHTS = {
    "on_time_delivery_rate": 0.40,
    "avg_delay_days": 0.25,
    "cancellation_rate": 0.20,
    "quality_score": 0.10,
    "delay_trend": 0.05
}

# Hybrid blend weights
HYBRID_WEIGHTS = {
    "rule_based": 0.60,
    "isolation_forest": 0.40
}

# ============================================================================
# DATA LOADING
# ============================================================================

def load_data():
    """Load all required CSV files."""
    print("Loading data files...")
    suppliers = pd.read_csv(DATA_DIR / "suppliers.csv")
    purchase_orders = pd.read_csv(DATA_DIR / "purchase_orders.csv")
    shipments = pd.read_csv(DATA_DIR / "shipments.csv")
    
    print(f"  - Loaded {len(suppliers)} suppliers")
    print(f"  - Loaded {len(purchase_orders)} purchase orders")
    print(f"  - Loaded {len(shipments)} shipments")
    
    return suppliers, purchase_orders, shipments


# ============================================================================
# FEATURE COMPUTATION
# ============================================================================

def compute_rule_based_features(suppliers, purchase_orders, shipments):
    """
    Compute rule-based features for each supplier.
    
    Returns:
        DataFrame with columns: supplier_id, on_time_delivery_rate, avg_delay_days,
                                cancellation_rate, quality_score, delay_trend
    """
    print("\nComputing rule-based features...")
    
    # Merge POs with shipments to get actual delivery dates
    # Use suffixes to distinguish PO status from shipment status
    po_with_shipments = purchase_orders.merge(
        shipments,
        on="po_id",
        how="left",
        suffixes=("_po", "_shipment")
    )
    
    features = []
    
    for supplier_id in suppliers["supplier_id"].unique():
        supplier_pos = po_with_shipments[po_with_shipments["supplier_id"] == supplier_id].copy()
        
        # 1. On-time delivery rate
        if len(supplier_pos) > 0:
            # Only consider delivered POs for on-time rate
            delivered_pos = supplier_pos[supplier_pos["status_po"] == "delivered"].copy()
            
            if len(delivered_pos) > 0:
                delivered_pos["promised_delivery_date"] = pd.to_datetime(
                    delivered_pos["promised_delivery_date"]
                )
                delivered_pos["actual_delivery_date"] = pd.to_datetime(
                    delivered_pos["actual_delivery_date"]
                )
                
                on_time = (
                    delivered_pos["actual_delivery_date"] 
                    <= delivered_pos["promised_delivery_date"]
                ).sum()
                on_time_rate = (on_time / len(delivered_pos)) * 100
            else:
                on_time_rate = 100.0  # No delivered POs yet
        else:
            on_time_rate = 100.0  # No POs yet
        
        # 2. Average delay days (only for delayed deliveries)
        if len(supplier_pos) > 0:
            delivered_pos = supplier_pos[supplier_pos["status_po"] == "delivered"].copy()
            
            if len(delivered_pos) > 0:
                delivered_pos["promised_delivery_date"] = pd.to_datetime(
                    delivered_pos["promised_delivery_date"]
                )
                delivered_pos["actual_delivery_date"] = pd.to_datetime(
                    delivered_pos["actual_delivery_date"]
                )
                
                delivered_pos["delay_days"] = (
                    delivered_pos["actual_delivery_date"] 
                    - delivered_pos["promised_delivery_date"]
                ).dt.days
                
                delayed = delivered_pos[delivered_pos["delay_days"] > 0]
                if len(delayed) > 0:
                    avg_delay = delayed["delay_days"].mean()
                else:
                    avg_delay = 0.0
            else:
                avg_delay = 0.0
        else:
            avg_delay = 0.0
        
        # 3. Cancellation rate
        if len(supplier_pos) > 0:
            cancelled = (supplier_pos["status_po"] == "cancelled").sum()
            cancellation_rate = (cancelled / len(supplier_pos)) * 100
        else:
            cancellation_rate = 0.0
        
        # 4. Quality score (from suppliers table, normalized to 0-100)
        quality_score_raw = suppliers[
            suppliers["supplier_id"] == supplier_id
        ]["quality_score"].values[0]
        # Assuming quality_score is already 0-100
        quality_score = quality_score_raw
        
        # 5. Delay trend (recent 60 days vs. earlier)
        if len(supplier_pos) > 0:
            delivered_pos = supplier_pos[supplier_pos["status_po"] == "delivered"].copy()
            
            if len(delivered_pos) > 1:
                delivered_pos["actual_delivery_date"] = pd.to_datetime(
                    delivered_pos["actual_delivery_date"]
                )
                delivered_pos["promised_delivery_date"] = pd.to_datetime(
                    delivered_pos["promised_delivery_date"]
                )
                
                # Split into recent (last 60 days) and prior
                max_date = delivered_pos["actual_delivery_date"].max()
                cutoff_date = max_date - timedelta(days=60)
                
                recent = delivered_pos[delivered_pos["actual_delivery_date"] >= cutoff_date]
                prior = delivered_pos[delivered_pos["actual_delivery_date"] < cutoff_date]
                
                recent["delay_days"] = (
                    recent["actual_delivery_date"] - recent["promised_delivery_date"]
                ).dt.days
                prior["delay_days"] = (
                    prior["actual_delivery_date"] - prior["promised_delivery_date"]
                ).dt.days
                
                recent_avg_delay = recent["delay_days"].mean() if len(recent) > 0 else 0.0
                prior_avg_delay = prior["delay_days"].mean() if len(prior) > 0 else 0.0
                
                # Trend: (recent - prior) / max(prior, 1)
                delay_trend = (recent_avg_delay - prior_avg_delay) / max(prior_avg_delay, 1)
            else:
                delay_trend = 0.0
        else:
            delay_trend = 0.0
        
        features.append({
            "supplier_id": supplier_id,
            "on_time_delivery_rate": on_time_rate,
            "avg_delay_days": avg_delay,
            "cancellation_rate": cancellation_rate,
            "quality_score": quality_score,
            "delay_trend": delay_trend
        })
    
    features_df = pd.DataFrame(features)
    print(f"  - Computed features for {len(features_df)} suppliers")
    
    return features_df


def compute_rule_based_score(features_df):
    """
    Compute rule-based composite score using weighted formula.
    
    Rule-based score combines:
    - on_time_delivery_rate (40%, higher is better)
    - avg_delay_days (25%, lower is better)
    - cancellation_rate (20%, lower is better)
    - quality_score (10%, higher is better)
    - delay_trend (5%, lower/negative is better)
    
    Returns:
        Series of rule-based scores (0-100)
    """
    print("\nComputing rule-based composite scores...")
    
    # Normalize each feature to 0-1 scale, accounting for direction
    
    # on_time_delivery_rate: higher is better (already 0-100, normalize to 0-1)
    on_time_norm = features_df["on_time_delivery_rate"] / 100.0
    
    # avg_delay_days: lower is better (0 is best, higher is worse)
    # Cap at 30 days for normalization, then invert
    avg_delay_capped = features_df["avg_delay_days"].clip(0, 30)
    avg_delay_norm = 1.0 - (avg_delay_capped / 30.0)
    
    # cancellation_rate: lower is better (0-100, normalize to 0-1, then invert)
    cancel_norm = 1.0 - (features_df["cancellation_rate"] / 100.0)
    
    # quality_score: higher is better (normalize to 0-1)
    quality_norm = features_df["quality_score"] / 100.0
    
    # delay_trend: lower/negative is better (can be negative, cap range)
    # Range approximately -1 to +1, normalize to 0-1 with inversion
    delay_trend_capped = features_df["delay_trend"].clip(-1, 1)
    delay_trend_norm = 1.0 - ((delay_trend_capped + 1) / 2.0)
    
    # Compute weighted score
    rule_score = (
        on_time_norm * RULE_WEIGHTS["on_time_delivery_rate"] +
        avg_delay_norm * RULE_WEIGHTS["avg_delay_days"] +
        cancel_norm * RULE_WEIGHTS["cancellation_rate"] +
        quality_norm * RULE_WEIGHTS["quality_score"] +
        delay_trend_norm * RULE_WEIGHTS["delay_trend"]
    )
    
    # Convert from 0-1 to 0-100 (0 = no risk, 100 = maximum risk)
    # Invert: lower on-time/quality = higher risk
    rule_score_100 = (1.0 - rule_score) * 100.0
    
    return rule_score_100


def compute_isolation_forest_score(features_df):
    """
    Apply Isolation Forest to detect anomalous supplier behavior patterns.
    
    Returns:
        Series of anomaly scores (0-1, higher = more anomalous = riskier)
    """
    print("\nApplying Isolation Forest anomaly detection...")
    
    # Select features for ML model
    feature_cols = [
        "on_time_delivery_rate",
        "avg_delay_days",
        "cancellation_rate",
        "quality_score",
        "delay_trend"
    ]
    
    X = features_df[feature_cols].values
    
    # Fit Isolation Forest
    iso_forest = IsolationForest(
        contamination=0.1,  # Assume ~10% are anomalous
        random_state=42,
        n_estimators=100
    )
    
    # Fit the model
    iso_forest.fit(X)
    
    # Get anomaly scores (-1 for outliers, 1 for inliers)
    # Convert to 0-1 scale where 0 = normal, 1 = highly anomalous
    anomaly_raw = iso_forest.score_samples(X)
    
    # Normalize: min score maps to 1 (most anomalous), max score maps to 0 (least anomalous)
    min_score = anomaly_raw.min()
    max_score = anomaly_raw.max()
    
    if max_score == min_score:
        # All scores are the same
        anomaly_normalized = np.zeros_like(anomaly_raw, dtype=float)
    else:
        anomaly_normalized = (max_score - anomaly_raw) / (max_score - min_score)
    
    # Scale to 0-100 risk
    anomaly_score_100 = anomaly_normalized * 100.0
    
    return pd.Series(anomaly_score_100, index=features_df.index)


def compute_hybrid_risk_score(features_df, rule_scores, anomaly_scores):
    """
    Blend rule-based score (60%) and Isolation Forest anomaly score (40%)
    to compute final hybrid risk score.
    
    Returns:
        Series of hybrid risk scores (0-100)
    """
    print("\nComputing hybrid risk scores...")
    
    hybrid_score = (
        rule_scores * HYBRID_WEIGHTS["rule_based"] +
        anomaly_scores * HYBRID_WEIGHTS["isolation_forest"]
    )
    
    return hybrid_score


def assign_risk_tier(risk_score):
    """Assign risk tier based on score thresholds."""
    if risk_score < 25:
        return "Low"
    elif risk_score < 50:
        return "Medium"
    elif risk_score < 75:
        return "High"
    else:
        return "Critical"


# ============================================================================
# OUTPUT & VALIDATION
# ============================================================================

def generate_output(suppliers, features_df, rule_scores, anomaly_scores, hybrid_scores):
    """
    Generate output DataFrame and CSV file.
    
    Returns:
        DataFrame with all supplier risk scores
    """
    print("\nGenerating output...")
    
    # Merge with supplier names
    result_df = features_df.copy()
    result_df = result_df.merge(
        suppliers[["supplier_id", "supplier_name"]],
        on="supplier_id",
        how="left"
    )
    
    # Add scores
    result_df["rule_based_score"] = rule_scores.values
    result_df["isolation_forest_anomaly_score"] = anomaly_scores.values
    result_df["hybrid_risk_score"] = hybrid_scores.values
    result_df["risk_tier"] = hybrid_scores.apply(assign_risk_tier)
    
    # Reorder columns
    output_cols = [
        "supplier_id",
        "supplier_name",
        "on_time_delivery_rate",
        "avg_delay_days",
        "cancellation_rate",
        "quality_score",
        "delay_trend",
        "rule_based_score",
        "isolation_forest_anomaly_score",
        "hybrid_risk_score",
        "risk_tier"
    ]
    result_df = result_df[output_cols]
    
    # Save to CSV
    output_path = OUTPUT_DIR / "supplier_risk_scores.csv"
    result_df.to_csv(output_path, index=False)
    print(f"  - Saved {output_path}")
    
    return result_df


def validate_known_bad_suppliers(result_df):
    """
    Validate that known-bad suppliers are correctly flagged with High/Critical tiers.
    
    Prints detailed validation report.
    """
    print("\n" + "=" * 80)
    print("VALIDATION: KNOWN-BAD SUPPLIERS")
    print("=" * 80)
    
    print("\nExpected High/Critical Risk: SUP001-SUP005 (chronic lateness)")
    print("                            SUP006-SUP008 (declining quality)")
    print()
    
    validation_issues = []
    
    for supplier_id in KNOWN_BAD_SUPPLIERS:
        row = result_df[result_df["supplier_id"] == supplier_id]
        
        if len(row) == 0:
            print(f"{supplier_id}: NOT FOUND IN RESULTS")
            validation_issues.append(f"{supplier_id}: Not found")
            continue
        
        row = row.iloc[0]
        
        print(f"{supplier_id} ({row['supplier_name']}):")
        print(f"  On-Time Rate:       {row['on_time_delivery_rate']:.1f}%")
        print(f"  Avg Delay Days:     {row['avg_delay_days']:.1f}")
        print(f"  Cancellation Rate:  {row['cancellation_rate']:.1f}%")
        print(f"  Quality Score:      {row['quality_score']:.1f}/100")
        print(f"  Delay Trend:        {row['delay_trend']:.3f}")
        print(f"  Rule-Based Score:   {row['rule_based_score']:.1f}")
        print(f"  Anomaly Score:      {row['isolation_forest_anomaly_score']:.1f}")
        print(f"  Hybrid Risk Score:  {row['hybrid_risk_score']:.1f}")
        print(f"  Risk Tier:          {row['risk_tier']}")
        
        # Check if properly flagged
        if row["risk_tier"] not in ["High", "Critical"]:
            msg = f"  [WARNING] BELOW HIGH TIER - Should be High/Critical but scored as {row['risk_tier']}"
            print(msg)
            validation_issues.append(f"{supplier_id}: {msg.strip()}")
        else:
            print(f"  [OK] Correctly flagged as {row['risk_tier']}")
        
        print()
    
    print("=" * 80)
    if validation_issues:
        print("VALIDATION FINDINGS:")
        for issue in validation_issues:
            print(f"  - {issue}")
    else:
        print("[OK] All known-bad suppliers correctly flagged with High/Critical tiers")
    print("=" * 80)
    
    return len(validation_issues) == 0


def print_full_summary(result_df):
    """Print detailed summary of all suppliers and their scores."""
    print("\n" + "=" * 80)
    print("FULL SUPPLIER RISK SCORE SUMMARY")
    print("=" * 80)
    print()
    
    # Group by risk tier
    for tier in ["Critical", "High", "Medium", "Low"]:
        tier_data = result_df[result_df["risk_tier"] == tier].sort_values(
            "hybrid_risk_score", ascending=False
        )
        
        if len(tier_data) == 0:
            continue
        
        print(f"\n{tier.upper()} RISK SUPPLIERS ({len(tier_data)}):")
        print("-" * 80)
        
        for _, row in tier_data.iterrows():
            print(f"{row['supplier_id']} | {row['supplier_name'][:30]:<30} | "
                  f"Score: {row['hybrid_risk_score']:6.1f} | "
                  f"OnTime: {row['on_time_delivery_rate']:5.1f}% | "
                  f"Delay: {row['avg_delay_days']:5.1f}d | "
                  f"Cancel: {row['cancellation_rate']:5.1f}%")
    
    print()
    print("=" * 80)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution flow."""
    print("\n" + "=" * 80)
    print("SUPPLYSENSE MODULE 2: SUPPLIER RISK ENGINE")
    print("=" * 80)
    
    # Load data
    suppliers, purchase_orders, shipments = load_data()
    
    # Compute rule-based features
    features_df = compute_rule_based_features(suppliers, purchase_orders, shipments)
    
    # Compute scores
    rule_scores = compute_rule_based_score(features_df)
    anomaly_scores = compute_isolation_forest_score(features_df)
    hybrid_scores = compute_hybrid_risk_score(features_df, rule_scores, anomaly_scores)
    
    # Generate output
    result_df = generate_output(
        suppliers, features_df, rule_scores, anomaly_scores, hybrid_scores
    )
    
    # Print full summary
    print_full_summary(result_df)
    
    # Validate known-bad suppliers
    validation_passed = validate_known_bad_suppliers(result_df)
    
    print("\n" + "=" * 80)
    print("RISK ENGINE EXECUTION COMPLETE")
    print("=" * 80)
    print(f"\nOutput file: {OUTPUT_DIR / 'supplier_risk_scores.csv'}")
    print(f"Total suppliers scored: {len(result_df)}")
    print(f"Validation status: {'PASSED' if validation_passed else 'ISSUES FOUND'}")
    print()


if __name__ == "__main__":
    main()
