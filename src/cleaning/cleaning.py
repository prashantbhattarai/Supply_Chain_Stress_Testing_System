"""Supplier table cleaning shared by generation and learning examples."""
import numpy as np
import pandas as pd


def clean_suppliers(df):
    """Copy, normalize headers, and validate supplier IDs and numeric values."""
    result = df.copy()
    result.columns = [str(column).strip().lower().replace(" ", "_") for column in result.columns]
    required = {"supplier_id", "lead_time", "reliability"}
    if not required.issubset(result.columns):
        raise ValueError("Suppliers need supplier_id, lead_time, and reliability")
    if result["supplier_id"].isna().any() or result["supplier_id"].duplicated().any():
        raise ValueError("Supplier IDs must be present and unique")
    for column in ("lead_time", "reliability"):
        result[column] = pd.to_numeric(result[column], errors="raise").astype(float)
        if not np.isfinite(result[column]).all():
            raise ValueError(f"{column} must contain finite numbers")
    if (result["lead_time"] < 0).any():
        raise ValueError("lead_time cannot be negative")
    if not result["reliability"].between(0, 1).all():
        raise ValueError("reliability must be between 0 and 1")
    return result
