import pandas as pd
import numpy as np

from src.cleaning.cleaning import clean_suppliers

np.random.seed(42)

def generate_suppliers(n= 50):
    df = pd.DataFrame({
        "supplier_id": range(1, n+1),
        "lead_time": np.random.randint(5, 40, size = n),
        "reliability": np.random.uniform(0.8, 0.99, size = n)
        })
    return clean_suppliers(df)

# testing the code
if __name__ == "__main__":
    raw_df = generate_suppliers(10)
    print ("Helow")
    print (raw_df)
    print (raw_df.describe())
