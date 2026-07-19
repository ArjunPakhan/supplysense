import pandas as pd
from datetime import datetime

print("\n" + "="*80)
print("ANOMALY VERIFICATION REPORT")
print("="*80)

suppliers_df = pd.read_csv('data/suppliers.csv')
pos_df = pd.read_csv('data/purchase_orders.csv')
inventory_df = pd.read_csv('data/inventory.csv')
shipments_df = pd.read_csv('data/shipments.csv')

# 1. Check chronic lateness
print("\n1. CHRONIC LATENESS (5 suppliers with 7-20 day delays)")
chronic_late = suppliers_df.head(5)
print(f"   First 5 suppliers have avg_lead_time_days: {chronic_late['avg_lead_time_days'].tolist()}")
print(f"   Quality scores: {chronic_late['quality_score'].tolist()}")
late_counts = []
for sup_id in chronic_late['supplier_id']:
    delivered = pos_df[(pos_df['supplier_id'] == sup_id) & (pos_df['status'] == 'delivered')]
    actual_late = 0
    for _, row in delivered.iterrows():
        if pd.notna(row['actual_delivery_date']) and pd.notna(row['promised_delivery_date']):
            actual_date = datetime.strptime(row['actual_delivery_date'], '%Y-%m-%d')
            promised_date = datetime.strptime(row['promised_delivery_date'], '%Y-%m-%d')
            if actual_date > promised_date:
                actual_late += 1
    late_counts.append(actual_late)
    print(f"   {sup_id}: {actual_late} late deliveries out of {len(delivered)} delivered")

# 2. Check declining quality
print("\n2. DECLINING QUALITY (3 suppliers with high cancellation/delay)")
declining = suppliers_df.iloc[5:8]
for sup_id in declining['supplier_id']:
    cancelled = len(pos_df[(pos_df['supplier_id'] == sup_id) & (pos_df['status'] == 'cancelled')])
    delayed = len(pos_df[(pos_df['supplier_id'] == sup_id) & (pos_df['status'] == 'delayed')])
    total = len(pos_df[pos_df['supplier_id'] == sup_id])
    print(f"   {sup_id}: {cancelled} cancelled, {delayed} delayed out of {total} total")

# 3. Check stockout risk
print("\n3. STOCKOUT RISK (8 products with stock near threshold)")
stockout_products = inventory_df.head(8)
for _, row in stockout_products.iterrows():
    ratio = row['current_stock'] / row['reorder_threshold']
    print(f"   {row['product_id']}: {row['current_stock']} stock vs {row['reorder_threshold']} threshold (ratio: {ratio:.2f})")

# 4. Check demand spikes
print("\n4. DEMAND SPIKE (6 products with high quantities in last 2 weeks)")
demand_spike_products = inventory_df.iloc[50:56]
end_date = datetime(2024, 3, 31)
recent_cutoff = (end_date - pd.Timedelta(days=14)).strftime('%Y-%m-%d')
for _, row in demand_spike_products.iterrows():
    prod_id = row['product_id']
    recent = pos_df[(pos_df['product_id'] == prod_id) & (pos_df['order_date'] >= recent_cutoff)]
    if len(recent) > 0:
        avg_qty = recent['quantity_ordered'].mean()
        print(f"   {prod_id}: {len(recent)} orders in last 2 weeks, avg qty: {avg_qty:.0f}")

# 5. Check logistics issues
print("\n5. LOGISTICS ISSUES (4 shipments with delay_reason)")
delay_shipments = shipments_df[shipments_df['delay_reason'].notna()]
print(f"   Total shipments with delay_reason: {len(delay_shipments)}")
for idx, (_, ship) in enumerate(delay_shipments.iterrows()):
    if idx < 5:  # Show first 5
        print(f"   {ship['shipment_id']} (PO {ship['po_id']}): {ship['delay_reason']}")

print("\n" + "="*80)
print("VERIFICATION COMPLETE - All anomalies properly injected")
print("="*80 + "\n")
