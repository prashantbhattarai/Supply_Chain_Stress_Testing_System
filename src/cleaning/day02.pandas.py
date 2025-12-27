import pandas as pd

# Dataframe
df = pd.DataFrame({
    "supplier":  ["A", "B", "C", "D"],
    "lead_time":  [10, 20, 15, 12],
    "reliability": [0.95, 0.9, 0.85, 0.92]
})

print("Describe the DataFrame:")
print(df.describe())

print("Filter Supplier with lead time > 12:")
print(df[df["lead_time"] > 12])

# Handeling the missing values:
df_missing = df.copy()
print(df_missing)
df_missing.loc[1, "lead_time"] = None
print(df_missing)
# it prints NAN value, ie none in the first index of the lead_time

df_missing["lead_time"].fillna(df_missing["lead_time"].mean())
print("\n After filling the missing lead_time:")
print(df_missing)

# Merge example
ports = pd.DataFrame({
    "supplier": ["A", "B", "C", "D"],
    "port": ["Port1", "Port2", "Port3", "Port4"]
})

merged_df = df.merge(ports, on ="supplier", how = "left")
print("\n Merged DataFrame with ports:")
print(merged_df)

""" In this day I created a dataframe , describe its stats, 
filter some of the data, and also add missing values to some values
 and finally merge another key to my dataframe which helps me learn
 basics of dataframe manipulations"""
