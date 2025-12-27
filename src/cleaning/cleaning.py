import pandas as pd

def clean_suppliers(df):
    df = df.copy()
    df.columns = df.columns.str.lower().str.replace(" ", "_")
    df["lead_time"] = df["lead_time"].astype(float)
    df["reliability"] = df["reliability"].astype(float)
    return df

# testing using a random dataframe

data = {
    "Supplier_ID": [1000, 3222, 3232],
    "Lead time": [5, 7, 3],
    "Reliability": [0.9, 0.8, 0.95]
}

df = pd.DataFrame(data)
print("\nMessy Data:\n", df)
print("\nCleaned Data:\n", clean_suppliers(df))
