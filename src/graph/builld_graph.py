"""Backward-compatible alias (typo in module name). Prefer ``build_graph``."""
from src.graph.build_graph import build_graph

__all__ = ["build_graph"]
