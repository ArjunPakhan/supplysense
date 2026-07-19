import pandas as pd
import os

files = ['suppliers.csv', 'purchase_orders.csv', 'inventory.csv', 'shipments.csv']
print("\n[CSV FILE VERIFICATION]")
for f in files:
    path = f'data/{f}'
    if os.path.exists(path):
        df = pd.read_csv(path)
        print(f"\n{f}:")
        print(f"  Rows: {len(df)}")
        print(f"  Columns: {list(df.columns)}")
        print(f"  Sample row:")
        print(f"    {df.iloc[0].to_dict()}")
