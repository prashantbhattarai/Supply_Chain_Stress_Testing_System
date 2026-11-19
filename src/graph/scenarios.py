"""Deterministic disruption and rerouting for a versioned network snapshot."""

import math
from typing import Optional

import networkx as nx
import pandas as pd

from src.domain import (
    ConditionTrials, Delivery, Disruption, Edge, EdgeDelay, NetworkSnapshot,
    NodeOutage, RouteClosure, Scenario, Shipment, TransportSlowdown,
    validate_scenario,
)
from src.graph.build_graph import build_graph
from src.graph.graph_analysis import shortest_path_metrics


def build_snapshot_graph(network: NetworkSnapshot) -> nx.DiGraph:
    """Adapt stored network records to the Phase 1 builder."""
    suppliers = pd.DataFrame(
        ((node.node_id, node.lead_time_days, node.reliability, node.display_name)
         for node in network.nodes),
        columns=["supplier_id", "lead_time", "reliability", "display_name"],
    )
    routes = pd.DataFrame(
        ((edge.origin_id, edge.destination_id, edge.transit_hours) for edge in network.edges),
        columns=["origin", "destination", "time"],
    )
    return build_graph(routes, suppliers)


def apply_disruption(
    baseline: nx.DiGraph, disruption: Disruption, *, allow_unavailable: bool = False,
) -> nx.DiGraph:
    """Apply a shock on a copy. A prevalidated target may already be unavailable."""
    stressed = baseline.copy()
    if isinstance(disruption, NodeOutage):
        if disruption.node_id not in stressed:
            if allow_unavailable:
                return stressed
            raise ValueError("Outage node must exist in the graph")
        stressed.remove_node(disruption.node_id)
        return stressed

    if not isinstance(disruption, (RouteClosure, EdgeDelay, TransportSlowdown)):
        raise ValueError("Unknown disruption type")
    origin, destination = disruption.origin_id, disruption.destination_id
    if not stressed.has_edge(origin, destination):
        if allow_unavailable:
            return stressed
        raise ValueError("Disrupted route must exist in the graph")
    if isinstance(disruption, RouteClosure):
        stressed.remove_edge(origin, destination)
    else:
        attributes = stressed[origin][destination]
        hours = attributes["time"]
        if isinstance(disruption, EdgeDelay):
            hours += disruption.added_hours
        else:
            hours *= disruption.factor
        if not math.isfinite(hours):
            raise ValueError("Disrupted route time must remain finite")
        attributes["time"] = hours
    return stressed


def evaluate_delivery(graph: nx.DiGraph, shipment: Shipment) -> Delivery:
    """Evaluate the fastest available shipment path after endpoint validation."""
    path = shortest_path_metrics(graph, shipment.origin_id, shipment.destination_id)
    if path.path is None:
        return Delivery(None, None, None)
    readiness = 24 * graph.nodes[shipment.origin_id]["lead_time"]
    return Delivery(path.path, path.total_time, readiness + path.total_time)


def add_backup_routes(stressed: nx.DiGraph, backup_edges: tuple[Edge, ...]) -> nx.DiGraph:
    """Add prevalidated backup edges whose endpoints survived stress."""
    mitigated = stressed.copy()
    for edge in backup_edges:
        origin, destination = edge.endpoints
        if origin in stressed and destination in stressed:
            mitigated.add_edge(origin, destination, time=edge.transit_hours)
    return mitigated


def _uses_backup(path: tuple[int, ...], added: set[tuple[int, int]]) -> bool:
    return any(pair in added for pair in zip(path, path[1:]))


def _validate_backup(
    graph: nx.DiGraph, shipment: Shipment, added: set[tuple[int, int]],
    fastest_path: Optional[tuple[int, ...]],
) -> None:
    origin, destination = shipment.origin_id, shipment.destination_id
    if origin not in graph or destination not in graph:
        # The shipment is explicitly unserved when either endpoint is out.
        return
    if fastest_path is not None:
        if _uses_backup(fastest_path, added):
            return
        # A valid alternative can be slower than the best surviving route.
        reachable = nx.descendants(graph, origin) | {origin}
        reaches_destination = nx.ancestors(graph, destination) | {destination}
        relevant = reachable & reaches_destination
        if any(a in relevant and b in relevant for a, b in added):
            paths = nx.all_simple_paths(graph.subgraph(relevant), origin, destination)
            if any(_uses_backup(path, added) for path in paths):
                return
    raise ValueError("Backup routes must add a shipment path under stress")


def prepare_scenario(
    network: NetworkSnapshot, shipment: Shipment, scenario: Scenario,
) -> tuple[nx.DiGraph, nx.DiGraph, nx.DiGraph]:
    """Validate and build the three base graphs before evaluating outcomes."""
    validate_scenario(network, shipment, scenario)
    baseline = build_snapshot_graph(network)
    stressed = apply_disruption(baseline, scenario.disruption)
    mitigated = add_backup_routes(stressed, scenario.backup_edges)
    added = {edge.endpoints for edge in scenario.backup_edges if mitigated.has_edge(*edge.endpoints)}
    fastest = shortest_path_metrics(mitigated, shipment.origin_id, shipment.destination_id)
    _validate_backup(mitigated, shipment, added, fastest.path)
    return baseline, stressed, mitigated


def deterministic(network: NetworkSnapshot, shipment: Shipment, scenario: Scenario) -> ConditionTrials:
    """Return one baseline, stressed, and mitigated delivery on independent graphs."""
    baseline, stressed, mitigated = prepare_scenario(network, shipment, scenario)
    return ConditionTrials(
        (evaluate_delivery(baseline, shipment),),
        (evaluate_delivery(stressed, shipment),),
        (evaluate_delivery(mitigated, shipment),),
    )
