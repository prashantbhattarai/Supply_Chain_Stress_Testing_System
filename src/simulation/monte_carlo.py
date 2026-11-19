"""Replayable Monte Carlo comparisons using common random samples.

Background node availability and route times are mutually independent. Each
trial routes with full knowledge of availability and sampled times, which is
an optimistic rerouting assumption.
"""

import platform
from dataclasses import dataclass, replace
from typing import Literal

import networkx as nx
import numpy as np
import pandas as pd

from src.domain import (
    MONTE_CARLO_VERSION, ConditionTrials, Delivery, Edge, NetworkRef, NodeOutage,
    NetworkSnapshot, RunSettings,
)
from src.graph.scenarios import add_backup_routes, apply_disruption, evaluate_delivery, prepare_scenario

MAX_NODES = 25
MAX_EDGES = 60
MAX_TRIALS = 10_000
MAX_SENSITIVITY_CANDIDATES = 8
MAX_SENSITIVITY_TRIALS = 500
Outcome = Literal["on_time", "late", "unserved"]


@dataclass(frozen=True)
class SimulationMetadata:
    network: NetworkRef
    settings: RunSettings
    python_version: str
    numpy_version: str
    pandas_version: str
    networkx_version: str


@dataclass(frozen=True)
class SimulationResult(ConditionTrials):
    metadata: SimulationMetadata

    @property
    def statuses(self) -> dict[str, tuple[Outcome, ...]]:
        """Return one status per recorded trial using the saved deadline."""
        deadline = self.metadata.settings.shipment.deadline_hours
        return {
            "baseline": tuple(delivery.status(deadline) for delivery in self.baseline),
            "stressed": tuple(delivery.status(deadline) for delivery in self.stressed),
            "mitigated": tuple(delivery.status(deadline) for delivery in self.mitigated),
        }


@dataclass(frozen=True)
class _TrialSamples:
    availability: dict[int, np.ndarray]
    transport_hours: dict[tuple[int, int], np.ndarray]


def _samples(network: NetworkSnapshot, settings: RunSettings) -> _TrialSamples:
    root = np.random.default_rng(settings.seed)
    entropy = root.integers(0, 2**32, size=4, dtype=np.uint32).tolist()

    def stream(kind: int, *ids: int) -> np.random.Generator:
        # Separate namespaces and encode signed IDs without Python's process hash.
        words = [*entropy, kind]
        for node_id in ids:
            encoded = node_id + 2**63
            words.extend((encoded & 0xFFFFFFFF, encoded >> 32))
        return np.random.default_rng(words)

    availability = {
        node.node_id: stream(0, node.node_id).random(settings.trials) < node.reliability
        for node in network.nodes
    }
    transport = {}
    for edge in (*network.edges, *settings.scenario.backup_edges):
        z = stream(1, *edge.endpoints).standard_normal(settings.trials)
        with np.errstate(over="ignore", under="ignore"):
            hours = edge.transit_hours * np.exp(settings.sigma * z - settings.sigma**2 / 2)
        if not np.isfinite(hours).all():
            raise ValueError(f"Sampled route time must remain finite: {edge.endpoints}")
        transport[edge.endpoints] = hours
    return _TrialSamples(availability, transport)


def _validate_workload(network: NetworkSnapshot, settings: RunSettings) -> None:
    if not isinstance(network, NetworkSnapshot) or not isinstance(settings, RunSettings):
        raise ValueError("A validated network snapshot and run settings are required")
    if len(network.nodes) > MAX_NODES:
        raise ValueError(f"At most {MAX_NODES} nodes are supported")
    if len(network.edges) + len(settings.scenario.backup_edges) > MAX_EDGES:
        raise ValueError(f"At most {MAX_EDGES} distinct routes, including backups, are supported")
    if settings.trials > MAX_TRIALS:
        raise ValueError(f"At most {MAX_TRIALS} trials are supported")
    if settings.algorithm_version != MONTE_CARLO_VERSION or settings.edge_jitter_fraction != 0:
        raise ValueError("Unsupported simulation algorithm or legacy jitter setting")


def _available_graph(baseline: nx.DiGraph, samples: _TrialSamples, trial: int) -> nx.DiGraph:
    available = baseline.copy()
    available.remove_nodes_from(node for node, draws in samples.availability.items() if not draws[trial])
    for origin, destination, data in available.edges(data=True):
        data["time"] = float(samples.transport_hours[origin, destination][trial])
    return available


def _trial_graphs(
    baseline: nx.DiGraph, settings: RunSettings, samples: _TrialSamples, trial: int,
) -> dict[str, nx.DiGraph]:
    available = _available_graph(baseline, samples, trial)
    stressed = apply_disruption(available, settings.scenario.disruption, allow_unavailable=True)
    backup = tuple(
        Edge(*edge.endpoints, float(samples.transport_hours[edge.endpoints][trial]))
        for edge in settings.scenario.backup_edges
        if all(node in stressed for node in edge.endpoints)
    )
    return {
        "baseline": available,
        "stressed": stressed,
        "mitigated": add_backup_routes(stressed, backup),
    }


def simulate(network: NetworkSnapshot, settings: RunSettings) -> SimulationResult:
    """Evaluate baseline, stressed, and mitigated trials using identical entity draws."""
    _validate_workload(network, settings)
    baseline, _, _ = prepare_scenario(network, settings.shipment, settings.scenario)
    samples = _samples(network, settings)
    results: dict[str, list[Delivery]] = {"baseline": [], "stressed": [], "mitigated": []}
    for trial in range(settings.trials):
        for condition, graph in _trial_graphs(baseline, settings, samples, trial).items():
            results[condition].append(evaluate_delivery(graph, settings.shipment))
    return SimulationResult(
        tuple(results["baseline"]), tuple(results["stressed"]), tuple(results["mitigated"]),
        SimulationMetadata(
            network.ref, settings, platform.python_version(), np.__version__,
            pd.__version__, nx.__version__,
        ),
    )



def sample_node_outages(
    network: NetworkSnapshot, settings: RunSettings, candidate_ids: tuple[int, ...], trial_count: int,
) -> tuple[tuple[Delivery, ...], dict[int, tuple[Delivery, ...]]]:
    """Evaluate single-node outages on a prefix of the original baseline samples."""
    _validate_workload(network, settings)
    if type(trial_count) is not int or not 1 <= trial_count <= min(settings.trials, MAX_SENSITIVITY_TRIALS):
        raise ValueError("Sensitivity trials must be within the run and sensitivity trial budgets")
    if not isinstance(candidate_ids, tuple) or len(candidate_ids) > MAX_SENSITIVITY_CANDIDATES:
        raise ValueError(f"Provide a tuple of at most {MAX_SENSITIVITY_CANDIDATES} transit node IDs")
    baseline, _, _ = prepare_scenario(network, settings.shipment, settings.scenario)
    shipment = settings.shipment
    transit_ids = set(baseline) - {shipment.origin_id, shipment.destination_id}
    if any(type(node_id) is not int or node_id not in transit_ids for node_id in candidate_ids):
        raise ValueError("Sensitivity candidates must be transit nodes")
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("Sensitivity candidates must be unique")
    samples = _samples(network, replace(settings, trials=trial_count))
    matching_baseline = []
    outcomes: dict[int, list[Delivery]] = {node_id: [] for node_id in candidate_ids}
    outages = tuple(NodeOutage(node_id) for node_id in candidate_ids)
    for trial in range(trial_count):
        available = _available_graph(baseline, samples, trial)
        matching_baseline.append(evaluate_delivery(available, shipment))
        for outage in outages:
            disrupted = apply_disruption(available, outage, allow_unavailable=True)
            outcomes[outage.node_id].append(evaluate_delivery(disrupted, shipment))
    return tuple(matching_baseline), {node_id: tuple(deliveries) for node_id, deliveries in outcomes.items()}
