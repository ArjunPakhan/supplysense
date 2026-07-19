# SupplySense Synthetic Dataset Generation

## Overview
`data_generator.py` generates realistic synthetic supply chain datasets for the SupplySense hackathon project. The script creates 4 interconnected CSV files with injected anomalies that simulate real-world supply chain risk scenarios.

## Generated Datasets

### 1. suppliers.csv (25 suppliers)
- **Columns**: supplier_id, supplier_name, category, country, onboarded_date, avg_lead_time_days, quality_score, contract_value_annual
- **Purpose**: Master supplier table with baseline metrics
- **Key Fields**:
  - `category`: raw_materials, packaging, electronics, logistics_partner
  - `quality_score`: 0-100 (45-98 range; chronic late suppliers have lower scores)
  - `avg_lead_time_days`: baseline delivery time (inflated for problem suppliers)

### 2. purchase_orders.csv (800 POs)
- **Columns**: po_id, supplier_id, product_id, order_date, promised_delivery_date, actual_delivery_date, quantity_ordered, unit_cost, status
- **Purpose**: 6 months of purchase order history
- **Key Fields**:
  - `status`: delivered, in_transit, delayed, cancelled
  - `actual_delivery_date`: null for in_transit/delayed/cancelled orders
  - References both suppliers.csv and inventory.csv via foreign keys

### 3. inventory.csv (60 products)
- **Columns**: product_id, product_name, category, warehouse_id, current_stock, reorder_threshold, max_capacity, avg_daily_demand, last_restock_date
- **Purpose**: Current inventory state across 4 warehouses (WH1-WH4)
- **Key Fields**:
  - `reorder_threshold`: minimum stock level before automatic reorder
  - `current_stock`: snapshot at 2024-03-31
  - `avg_daily_demand`: used for lead time calculations

### 4. shipments.csv (730 shipments)
- **Columns**: shipment_id, po_id, carrier_name, dispatch_date, expected_arrival_date, actual_arrival_date, delay_reason, status
- **Purpose**: Shipment tracking for delivered, in_transit, and delayed POs
- **Key Fields**:
  - `delay_reason`: weather, customs, carrier_issue, or null/"none" for on-time
  - `status`: mirrors PO status

## Injected Anomalies for Risk Analysis

### 1. Chronic Lateness Pattern (5 suppliers)
**Suppliers**: SUP001, SUP002, SUP003, SUP004, SUP005

- **Characteristic**: 100% of their delivered orders arrive 7-20 days AFTER promised_delivery_date
- **Evidence**: 
  - avg_lead_time_days inflated (36-49 days vs 5-35 for normal suppliers)
  - quality_score lower (52-68 vs 70-98 for normal suppliers)
  - PO status shows "delivered" but actual_delivery_date > promised_delivery_date

### 2. Declining Quality Pattern (3 suppliers)
**Suppliers**: SUP006, SUP007, SUP008

- **Characteristic**: Higher rates of cancellation (7-9 per supplier) and delay (6-15 per supplier)
- **Evidence**:
  - SUP006: 9 cancelled, 15 delayed out of 34 total
  - SUP007: 8 cancelled, 6 delayed out of 24 total
  - SUP008: 7 cancelled, 12 delayed out of 32 total
- **Impact**: Risk flags for contract review / alternative sourcing

### 3. Stockout Risk (8 products)
**Products**: PROD0001-PROD0008

- **Characteristic**: current_stock near or below reorder_threshold given avg_daily_demand
- **Evidence**:
  - PROD0003: 78 stock vs 270 threshold (0.29 ratio)
  - PROD0004: 77 stock vs 185 threshold (0.42 ratio)
  - PROD0005: 77 stock vs 127 threshold (0.61 ratio)
- **Impact**: Immediate replenishment required; stockout risk in 2-5 days

### 4. Demand Spike (6 products)
**Products**: PROD0051-PROD0056

- **Characteristic**: Notably higher order quantities in last 2 weeks (last 14 days of dataset)
- **Evidence**:
  - PROD0052: avg 482 units/order (vs typical 20-200)
  - PROD0054: avg 390 units/order
  - PROD0055: avg 333 units/order
  - PROD0056: avg 480 units/order
- **Impact**: Potential supply chain disruption, forecast accuracy issues

### 5. Logistics Issues (4 shipments with delay_reason)
**Sample Shipments**: SHIP000010, SHIP000161, SHIP000192, SHIP000197

- **Characteristic**: Documented delay reasons in shipments table
- **Delay Reasons**: weather, customs, carrier_issue
- **Evidence**: delay_reason field populated (vs. null/"none" for normal shipments)
- **Impact**: Root cause tracking for delayed shipments

## Usage

```bash
python data_generator.py
```

**Output**:
- Creates `/data` directory with 4 CSV files
- Prints summary with row counts and detailed anomaly list
- Uses random_state=42 for reproducible results

## Key Features

✓ **Reproducible**: Fixed random seed (42) ensures consistent output  
✓ **Referential Integrity**: supplier_id and product_id properly linked across tables  
✓ **Realistic Patterns**: 6-month historical data with seasonal variations  
✓ **Injection Precision**: Each anomaly category explicitly tracked and verified  
✓ **Warehouse Distribution**: 4 warehouses (WH1-WH4) for multi-location scenarios  
✓ **Status Realism**: Null values for actual_delivery_date on in_transit/delayed orders  

## Data Statistics

| Dataset | Rows | Date Range | References |
|---------|------|-----------|-----------|
| suppliers.csv | 25 | Onboarded 2020-2024 | — |
| purchase_orders.csv | 800 | 2023-10-03 to 2024-03-31 | supplier_id, product_id |
| inventory.csv | 60 | Snapshot 2024-03-31 | — |
| shipments.csv | 730 | 2023-10-04 to 2024-03-31 | po_id |

## Next Steps

These datasets are ready for:
- Risk scoring model development (Module 2)
- Natural language query processing (Module 3)
- Dashboard visualization (Module 4)
- Anomaly detection algorithm training

**Do NOT modify these CSVs manually** — regenerate with `data_generator.py` if adjustments needed.
