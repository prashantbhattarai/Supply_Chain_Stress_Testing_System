"""Dijkstra shortest-path analysis for directed, non-negative weights."""
from __future__ import annotations

from dataclasses import dataclass
import math

import networkx as nx


@dataclass(frozen=True)
class PathMetrics:
    """Path, transit hours, and an explicit status for unsuccessful queries."""
    path: tuple | None
    total_time: float | None
    status: str
    detail: str | None = None

    @property
    def is_connected(self):
        """True when a path exists, including a zero-length same-node path."""
        return self.path is not None


def shortest_path_metrics(graph, source, target, weight="time"):
    """Run Dijkstra once, returning both path and total weight.

    Missing endpoints and unreachable destinations return statuses, not exceptions.
    Missing, negative, or non-finite edge weights raise ValueError.
    """
    if not graph.is_directed() or graph.is_multigraph():
        raise ValueError("Expected a directed, simple graph")
    for _, _, data in graph.edges(data=True):
        value = data.get(weight)
        if value is None or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"Every edge needs a finite non-negative {weight} weight")
    if len(graph) == 0:
        return PathMetrics(None, None, "empty_graph", "Graph has no nodes.")
    if source not in graph:
        return PathMetrics(None, None, "missing_source", f"Source {source!r} is not in the graph.")
    if target not in graph:
        return PathMetrics(None, None, "missing_target", f"Target {target!r} is not in the graph.")
    if source == target:
        return PathMetrics((source,), 0.0, "same_node")
    try:
        total, path = nx.single_source_dijkstra(graph, source, target, weight=weight)
        return PathMetrics(tuple(path), float(total), "ok")
    except nx.NetworkXNoPath:
        return PathMetrics(None, None, "no_path", "No directed path exists.")


def _demo():
    """Print a repeatable example when executed as a module."""
    from src.data_generation.routes import generate_routes
    from src.graph.build_graph import build_graph
    print(shortest_path_metrics(build_graph(generate_routes(10, seed=42)), 1, 20))


if __name__ == "__main__":
    _demo()
