"""
SupplySense Data Generator
Generates 4 synthetic CSV datasets with realistic anomalies for supply chain risk analysis.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# Set random seed for reproducibility
np.random.seed(42)
random.seed(42)

# Configuration
SUPPLIERS_COUNT = 25
PURCHASE_ORDERS_COUNT = 800
PRODUCTS_COUNT = 60
WAREHOUSES = ['WH1', 'WH2', 'WH3', 'WH4']

# Date range for PO data: last 6 months
END_DATE = datetime(2024, 3, 31)
START_DATE = END_DATE - timedelta(days=180)


def generate_suppliers():
    """Generate suppliers.csv with 25 suppliers and inject chronic lateness patterns."""
    categories = ['raw_materials', 'packaging', 'electronics', 'logistics_partner']
    countries = ['China', 'Vietnam', 'Thailand', 'India', 'Germany', 'Mexico', 
                 'Brazil', 'USA', 'Poland', 'Indonesia']
    
    supplier_ids = [f'SUP{i:03d}' for i in range(1, SUPPLIERS_COUNT + 1)]
    suppliers = []
    
    # Suppliers with chronic lateness (5 suppliers)
    chronic_late_ids = supplier_ids[0:5]
    
    for supplier_id in supplier_ids:
        supplier_name = f"Supplier_{supplier_id}"
        category = np.random.choice(categories)
        country = np.random.choice(countries)
        onboarded_date = (END_DATE - timedelta(days=np.random.randint(365, 1825))).strftime('%Y-%m-%d')
        
        # Chronic late suppliers have longer lead times
        if supplier_id in chronic_late_ids:
            avg_lead_time = np.random.randint(35, 50)
            quality_score = np.random.randint(45, 70)
        else:
            avg_lead_time = np.random.randint(5, 35)
            quality_score = np.random.randint(70, 98)
        
        contract_value = np.random.randint(50000, 500000)
        
        suppliers.append({
            'supplier_id': supplier_id,
            'supplier_name': supplier_name,
            'category': category,
            'country': country,
            'onboarded_date': onboarded_date,
            'avg_lead_time_days': avg_lead_time,
            'quality_score': quality_score,
            'contract_value_annual': contract_value
        })
    
    df = pd.DataFrame(suppliers)
    df.to_csv('data/suppliers.csv', index=False)
    return df, chronic_late_ids


def generate_inventory():
    """Generate inventory.csv with products and inject stockout and demand spike anomalies."""
    product_categories = ['Electronics', 'Raw Materials', 'Packaging', 'Components', 'Finished Goods']
    product_ids = [f'PROD{i:04d}' for i in range(1, PRODUCTS_COUNT + 1)]
    
    # Identify products with anomalies
    stockout_risk_ids = product_ids[0:8]  # First 8 products trending to stockout
    demand_spike_ids = product_ids[50:56]  # Last 6 products with demand spike
    
    inventory = []
    for product_id in product_ids:
        product_name = f"Product_{product_id}"
        category = np.random.choice(product_categories)
        warehouse_id = np.random.choice(WAREHOUSES)
        
        if product_id in stockout_risk_ids:
            # Low stock near threshold
            reorder_threshold = np.random.randint(100, 300)
            current_stock = np.random.randint(50, reorder_threshold + 50)
            avg_daily_demand = np.random.randint(20, 60)
        else:
            avg_daily_demand = np.random.randint(5, 50)
            reorder_threshold = avg_daily_demand * np.random.randint(10, 30)
            current_stock = np.random.randint(reorder_threshold + 50, reorder_threshold + 300)
        
        max_capacity = current_stock + np.random.randint(200, 800)
        last_restock = (END_DATE - timedelta(days=np.random.randint(1, 60))).strftime('%Y-%m-%d')
        
        inventory.append({
            'product_id': product_id,
            'product_name': product_name,
            'category': category,
            'warehouse_id': warehouse_id,
            'current_stock': current_stock,
            'reorder_threshold': reorder_threshold,
            'max_capacity': max_capacity,
            'avg_daily_demand': avg_daily_demand,
            'last_restock_date': last_restock
        })
    
    df = pd.DataFrame(inventory)
    df.to_csv('data/inventory.csv', index=False)
    return df, stockout_risk_ids, demand_spike_ids


def generate_purchase_orders(suppliers_df, inventory_df, chronic_late_ids, demand_spike_ids):
    """Generate purchase_orders.csv with realistic delivery patterns and anomalies."""
    supplier_ids = suppliers_df['supplier_id'].tolist()
    product_ids = inventory_df['product_id'].tolist()
    
    # Suppliers with declining quality (3 suppliers)
    declining_quality_ids = supplier_ids[5:8]
    
    purchase_orders = []
    po_id_counter = 1
    
    # Generate 800 POs over 180 days
    for _ in range(PURCHASE_ORDERS_COUNT):
        po_id = f'PO{po_id_counter:05d}'
        po_id_counter += 1
        
        supplier_id = np.random.choice(supplier_ids)
        product_id = np.random.choice(product_ids)
        
        # Order date random within the 6-month window
        days_offset = np.random.randint(0, 180)
        order_date = (START_DATE + timedelta(days=days_offset)).strftime('%Y-%m-%d')
        
        # Promised delivery based on supplier's average lead time
        lead_time = int(suppliers_df[suppliers_df['supplier_id'] == supplier_id]['avg_lead_time_days'].values[0])
        promised_date = (datetime.strptime(order_date, '%Y-%m-%d') + timedelta(days=lead_time))
        promised_delivery_date = promised_date.strftime('%Y-%m-%d')
        
        # Determine quantity (with demand spike for certain products)
        if product_id in demand_spike_ids and days_offset > 165:  # Last 2 weeks
            quantity = np.random.randint(300, 600)
        else:
            quantity = np.random.randint(20, 200)
        
        unit_cost = np.random.randint(10, 500)
        
        # Determine status and actual delivery
        status_rand = np.random.random()
        
        if supplier_id in chronic_late_ids:
            # Chronic late: 60% delivered late, 30% in_transit, 10% cancelled
            if status_rand < 0.60:
                status = 'delivered'
                delay_days = np.random.randint(7, 20)
                actual_delivery_date = (promised_date + timedelta(days=delay_days)).strftime('%Y-%m-%d')
            elif status_rand < 0.90:
                status = 'in_transit'
                actual_delivery_date = None
            else:
                status = 'cancelled'
                actual_delivery_date = None
        elif supplier_id in declining_quality_ids:
            # Declining quality: more cancellations/delays
            if status_rand < 0.50:
                status = 'delivered'
                if np.random.random() < 0.3:  # 30% with minor delay
                    actual_delivery_date = (promised_date + timedelta(days=np.random.randint(1, 5))).strftime('%Y-%m-%d')
                else:
                    actual_delivery_date = promised_date.strftime('%Y-%m-%d')
            elif status_rand < 0.75:
                status = 'delayed'
                actual_delivery_date = None
            else:
                status = 'cancelled'
                actual_delivery_date = None
        else:
            # Normal suppliers: mostly on-time
            if status_rand < 0.85:
                status = 'delivered'
                if np.random.random() < 0.1:  # 10% with minor delay
                    actual_delivery_date = (promised_date + timedelta(days=np.random.randint(1, 3))).strftime('%Y-%m-%d')
                else:
                    actual_delivery_date = promised_date.strftime('%Y-%m-%d')
            elif status_rand < 0.95:
                status = 'in_transit'
                actual_delivery_date = None
            else:
                status = 'cancelled'
                actual_delivery_date = None
        
        purchase_orders.append({
            'po_id': po_id,
            'supplier_id': supplier_id,
            'product_id': product_id,
            'order_date': order_date,
            'promised_delivery_date': promised_delivery_date,
            'actual_delivery_date': actual_delivery_date,
            'quantity_ordered': quantity,
            'unit_cost': unit_cost,
            'status': status
        })
    
    df = pd.DataFrame(purchase_orders)
    df.to_csv('data/purchase_orders.csv', index=False)
    return df, declining_quality_ids


def generate_shipments(purchase_orders_df):
    """Generate shipments.csv for delivered, delayed, and in_transit POs with realistic issues."""
    carriers = ['FedEx', 'UPS', 'DHL', 'XPO Logistics', 'J.B. Hunt', 'AmazonSCS', 'CH Robinson']
    delay_reasons = ['weather', 'customs', 'carrier_issue', 'none']
    
    # Get POs that need shipments (delivered, delayed, in_transit)
    relevant_pos = purchase_orders_df[
        purchase_orders_df['status'].isin(['delivered', 'delayed', 'in_transit'])
    ].copy()
    
    # Select 4 shipments to have delay_reason populated (real-world logistics issues)
    shipment_indices = np.random.choice(len(relevant_pos), size=4, replace=False)
    
    shipments = []
    shipment_id_counter = 1
    
    for idx, (_, po_row) in enumerate(relevant_pos.iterrows()):
        shipment_id = f'SHIP{shipment_id_counter:06d}'
        shipment_id_counter += 1
        
        po_id = po_row['po_id']
        carrier_name = np.random.choice(carriers)
        
        # Dispatch is typically 1-2 days after order
        order_date = datetime.strptime(po_row['order_date'], '%Y-%m-%d')
        dispatch_date = (order_date + timedelta(days=np.random.randint(1, 3))).strftime('%Y-%m-%d')
        
        # Expected arrival based on promised delivery
        expected_arrival = po_row['promised_delivery_date']
        
        # Actual arrival and delay reason
        if po_row['status'] == 'delivered':
            actual_arrival_date = po_row['actual_delivery_date']
            delay_reason = 'none'
        elif po_row['status'] == 'delayed':
            actual_arrival_date = None
            # 50% have delay reason, 50% unknown
            delay_reason = 'none' if np.random.random() < 0.5 else np.random.choice(delay_reasons[:-1])
        else:  # in_transit
            actual_arrival_date = None
            delay_reason = 'none'
        
        # Override: 4 specific shipments get delay reasons
        if idx in shipment_indices:
            delay_reason = np.random.choice(delay_reasons[:-1])  # Exclude 'none'
            if actual_arrival_date:
                # Delay reason for delivered items means they were delayed
                actual_arrival_date = (
                    datetime.strptime(expected_arrival, '%Y-%m-%d') + 
                    timedelta(days=np.random.randint(2, 8))
                ).strftime('%Y-%m-%d')
        
        status = po_row['status']
        
        shipments.append({
            'shipment_id': shipment_id,
            'po_id': po_id,
            'carrier_name': carrier_name,
            'dispatch_date': dispatch_date,
            'expected_arrival_date': expected_arrival,
            'actual_arrival_date': actual_arrival_date,
            'delay_reason': delay_reason if delay_reason != 'none' else None,
            'status': status
        })
    
    df = pd.DataFrame(shipments)
    df.to_csv('data/shipments.csv', index=False)
    return df


def print_summary(suppliers_df, pos_df, inventory_df, shipments_df, 
                  chronic_late_ids, declining_quality_ids, stockout_ids, demand_spike_ids):
    """Print a summary of generated data and injected anomalies."""
    print("\n" + "="*80)
    print("SupplySense Synthetic Dataset Generation Complete")
    print("="*80)
    
    print("\n[ROW COUNTS]")
    print(f"  suppliers.csv:         {len(suppliers_df)} rows")
    print(f"  purchase_orders.csv:   {len(pos_df)} rows")
    print(f"  inventory.csv:         {len(inventory_df)} rows (60 products x {len(inventory_df)//60} warehouse(s))")
    print(f"  shipments.csv:         {len(shipments_df)} rows")
    
    print("\n[INJECTED ANOMALIES FOR RISK ANALYSIS]")
    
    print("\n1. CHRONIC LATENESS PATTERN (5 suppliers)")
    print(f"   Suppliers with 7-20 day delays on promised delivery dates:")
    for sup_id in chronic_late_ids:
        sup_name = suppliers_df[suppliers_df['supplier_id'] == sup_id]['supplier_name'].values[0]
        late_count = len(pos_df[(pos_df['supplier_id'] == sup_id) & (pos_df['status'] == 'delivered')])
        print(f"     - {sup_id} ({sup_name}): {late_count} POs with late delivery")
    
    print("\n2. DECLINING QUALITY PATTERN (3 suppliers)")
    print(f"   Suppliers with higher cancellation/delay rates:")
    for sup_id in declining_quality_ids:
        sup_name = suppliers_df[suppliers_df['supplier_id'] == sup_id]['supplier_name'].values[0]
        cancelled = len(pos_df[(pos_df['supplier_id'] == sup_id) & (pos_df['status'] == 'cancelled')])
        delayed = len(pos_df[(pos_df['supplier_id'] == sup_id) & (pos_df['status'] == 'delayed')])
        print(f"     - {sup_id} ({sup_name}): {cancelled} cancelled, {delayed} delayed")
    
    print("\n3. STOCKOUT RISK (8 products trending toward stockout)")
    print(f"   Products with current_stock near/below reorder_threshold:")
    for prod_id in stockout_ids:
        prod_name = inventory_df[inventory_df['product_id'] == prod_id]['product_name'].values[0]
        current = inventory_df[inventory_df['product_id'] == prod_id]['current_stock'].values[0]
        threshold = inventory_df[inventory_df['product_id'] == prod_id]['reorder_threshold'].values[0]
        print(f"     - {prod_id} ({prod_name}): {current} in stock vs {threshold} threshold")
    
    print("\n4. DEMAND SPIKE (6 products with unusual spike in last 2 weeks)")
    print(f"   Products with notably higher order quantities in recent period:")
    for prod_id in demand_spike_ids:
        prod_name = inventory_df[inventory_df['product_id'] == prod_id]['product_name'].values[0]
        recent_orders = pos_df[
            (pos_df['product_id'] == prod_id) & 
            (pos_df['order_date'] >= (END_DATE - timedelta(days=14)).strftime('%Y-%m-%d'))
        ]
        avg_qty = recent_orders['quantity_ordered'].mean() if len(recent_orders) > 0 else 0
        print(f"     - {prod_id} ({prod_name}): avg recent quantity {avg_qty:.0f} units")
    
    print("\n5. LOGISTICS ISSUES (4 shipments with delay_reason)")
    delay_shipments = shipments_df[shipments_df['delay_reason'].notna()]
    for _, ship in delay_shipments.iterrows():
        print(f"     - {ship['shipment_id']} (PO {ship['po_id']}): {ship['delay_reason']}")
    
    print("\n" + "="*80)
    print("All CSV files saved to ./data/ folder")
    print("="*80 + "\n")


def main():
    """Main function to orchestrate data generation."""
    print("Generating SupplySense synthetic datasets...")
    
    # Generate suppliers
    suppliers_df, chronic_late_ids = generate_suppliers()
    print(f"[OK] Generated {len(suppliers_df)} suppliers")
    
    # Generate inventory
    inventory_df, stockout_ids, demand_spike_ids = generate_inventory()
    print(f"[OK] Generated {len(inventory_df)} inventory records")
    
    # Generate purchase orders
    pos_df, declining_quality_ids = generate_purchase_orders(
        suppliers_df, inventory_df, chronic_late_ids, demand_spike_ids
    )
    print(f"[OK] Generated {len(pos_df)} purchase orders")
    
    # Generate shipments
    shipments_df = generate_shipments(pos_df)
    print(f"[OK] Generated {len(shipments_df)} shipments")
    
    # Print summary
    print_summary(
        suppliers_df, pos_df, inventory_df, shipments_df,
        chronic_late_ids, declining_quality_ids, stockout_ids, demand_spike_ids
    )


if __name__ == '__main__':
    main()
