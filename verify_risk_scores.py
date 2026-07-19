#!/usr/bin/env python3
"""Quick verification of risk_engine.py output."""

import pandas as pd
import os

print("\n" + "="*80)
print("VERIFICATION: supplier_risk_scores.csv")
print("="*80)

# Check file exists
if not os.path.exists("data/supplier_risk_scores.csv"):
    print("ERROR: data/supplier_risk_scores.csv not found!")
    exit(1)

# Load CSV
df = pd.read_csv("data/supplier_risk_scores.csv")

print(f"\n[OK] CSV loaded successfully")
print(f"  Rows: {len(df)}")
print(f"  Columns: {len(df.columns)}")

# Verify columns
expected_cols = [
    'supplier_id', 'supplier_name', 'on_time_delivery_rate',
    'avg_delay_days', 'cancellation_rate', 'quality_score',
    'delay_trend', 'rule_based_score', 'isolation_forest_anomaly_score',
    'hybrid_risk_score', 'risk_tier'
]
if list(df.columns) == expected_cols:
    print("[OK] All expected columns present")
else:
    print("[ERROR] Column mismatch!")
    print(f"  Expected: {expected_cols}")
    print(f"  Got: {list(df.columns)}")

# Risk tier distribution
print("\n[OK] Risk Tier Distribution:")
tier_counts = df['risk_tier'].value_counts().sort_index()
for tier in ['Low', 'Medium', 'High', 'Critical']:
    count = tier_counts.get(tier, 0)
    pct = (count / len(df)) * 100
    print(f"  {tier:10s}: {count:2d} suppliers ({pct:5.1f}%)")

# Check known-bad suppliers
print("\n[OK] Known-Bad Suppliers Validation:")
known_bad = {
    'SUP001': 'High', 'SUP002': 'High', 'SUP003': 'High',
    'SUP004': 'High', 'SUP005': 'High',
    'SUP006': 'High', 'SUP007': 'High', 'SUP008': 'Medium'  # Note: SUP008 expected Medium
}

all_correct = True
for sup_id, expected_tier in known_bad.items():
    row = df[df['supplier_id'] == sup_id]
    if len(row) == 0:
        print(f"  {sup_id}: NOT FOUND")
        all_correct = False
    else:
        actual_tier = row.iloc[0]['risk_tier']
        score = row.iloc[0]['hybrid_risk_score']
        status = "[OK]" if actual_tier == expected_tier else "[WARN]"
        print(f"  {status} {sup_id}: {actual_tier:10s} (score: {score:6.1f}) - Expected: {expected_tier}")
        if actual_tier != expected_tier:
            all_correct = False

# Score ranges
print("\n[OK] Score Ranges:")
print(f"  Hybrid Risk Score:        {df['hybrid_risk_score'].min():.1f} - {df['hybrid_risk_score'].max():.1f}")
print(f"  Rule-Based Score:         {df['rule_based_score'].min():.1f} - {df['rule_based_score'].max():.1f}")
print(f"  Anomaly Score:            {df['isolation_forest_anomaly_score'].min():.1f} - {df['isolation_forest_anomaly_score'].max():.1f}")

# Top 5 highest risk
print("\n[OK] Top 5 Highest Risk Suppliers:")
top5 = df.nlargest(5, 'hybrid_risk_score')[
    ['supplier_id', 'supplier_name', 'hybrid_risk_score', 'on_time_delivery_rate', 'avg_delay_days', 'risk_tier']
]
for i, (_, row) in enumerate(top5.iterrows(), 1):
    print(f"  {i}. {row['supplier_id']} {row['supplier_name']:30s} Score: {row['hybrid_risk_score']:6.1f} Tier: {row['risk_tier']:10s}")

print("\n" + "="*80)
print("VERIFICATION COMPLETE")
print("="*80)

if all_correct and len(df) == 25:
    print("\n[OK] All checks passed!")
else:
    print("\n[WARN] Some issues found (see above)")

print()
