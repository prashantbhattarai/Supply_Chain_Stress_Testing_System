"""Generate repeatable synthetic supplier data without global random state."""
import numpy as np
import pandas as pd

from src.cleaning.cleaning import clean_suppliers


def generate_suppliers(n=50, seed=None):
    """Return n suppliers with IDs 1..n, lead times in days, and reliability."""
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError("n must be a non-negative integer")
    rng = np.random.default_rng(seed)
    suppliers = pd.DataFrame({
        "supplier_id": range(1, n + 1),
        "lead_time": rng.integers(5, 40, size=n),
        "reliability": rng.uniform(0.8, 0.99, size=n),
    })
    return clean_suppliers(suppliers)


if __name__ == "__main__":
    print(generate_suppliers(10, seed=42))
