"""
Load and normalize supply-chain route tables from in-memory uploads (no repo-relative paths).
Expected logical columns: origin, destination, time (edge weight).
"""
from __future__ import annotations

import io
from typing import BinaryIO

import pandas as pd
import numpy as np

_CANONICAL = ("origin", "destination", "time")

_ALIASES: dict[str, frozenset[str]] = {
    "origin": frozenset({"origin", "from", "source", "o", "src", "start", "orig"}),
    "destination": frozenset({"destination", "to", "target", "d", "dest", "end"}),
    "time": frozenset({"time", "duration", "travel_time", "cost", "weight", "lead_time", "transit"}),
}


def _standardize_column_key(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def normalize_routes_dataframe(df: pd.DataFrame | None) -> pd.DataFrame:
    """Map common column names to origin / destination / time; drop invalid rows."""
    if df is None or df.empty:
        return pd.DataFrame(columns=list(_CANONICAL))

    rename: dict[str, str] = {}
    used_std: set[str] = set()
    for col in df.columns:
        key = _standardize_column_key(str(col))
        for std, aliases in _ALIASES.items():
            if key in aliases and std not in used_std:
                rename[col] = std
                used_std.add(std)
                break

    out = df.rename(columns=rename)
    if not set(_CANONICAL).issubset(out.columns):
        missing = set(_CANONICAL) - set(out.columns)
        raise ValueError(
            f"Missing required columns after normalization: {sorted(missing)}. "
            f"Need origin, destination, and time (or common aliases: from/to/duration, etc.)."
        )

    out = out[list(_CANONICAL)].dropna(subset=["origin", "destination"])
    out = out.copy()
    out["time"] = pd.to_numeric(out["time"], errors="coerce")
    out = out.dropna(subset=["time"])
    out = out[np.isfinite(out["time"]) & (out["time"] >= 0)]
    return out.reset_index(drop=True)


def read_routes_csv_bytes(data: bytes) -> pd.DataFrame:
    """Parse CSV from raw bytes (works in Docker/Streamlit Cloud without disk paths)."""
    return normalize_routes_dataframe(pd.read_csv(io.BytesIO(data)))


def read_routes_csv_stream(buffer: BinaryIO) -> pd.DataFrame:
    return normalize_routes_dataframe(pd.read_csv(buffer))
