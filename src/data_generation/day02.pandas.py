# day02_pandas_implementation
"""
- Created suppliers DataFrame
- Performed EDA
- Identified high-risk suppliers
"""

 
import pandas as pd

# Dataset for suppliers
suppliers = pd.DataFrame({
    "suppliers_id":  [1, 2, 3, 4, 5],
    "suppliers_name": ["Alpha", "Beta", "Gamma", "Delta", 'Meta'],
    "lead_time": [10, 20, 30, 40, 50],
    "reliability": [0.95, 0.88, 0.92, 0.80, 0.97]
})

print ("\n=== Raw Data===")
print(suppliers)

print("\n=== Describe ===")
print (suppliers.describe())

# filter the risky suppliers
risky = suppliers[
    (suppliers["lead_time"] > 20) |
    (suppliers["reliability"] < 0.90)
]

print("\n=== Risky Suppliers ===")
print(risky)