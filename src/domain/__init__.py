"""Immutable backend records and validation."""

import hashlib
import json
import math
import sys
from dataclasses import asdict, dataclass
from typing import Literal, Optional, Union


def _integer(value, label, minimum=-(2**63)):
    if type(value) is not int or not minimum <= value < 2**63:
        raise ValueError(f"{label} must be an integer in [{minimum}, {2**63 - 1}]")


def _number(value, label, maximum=None):
    if (type(value) not in (int, float) or value < 0
            or value > sys.float_info.max
            or not math.isfinite(value) or (maximum is not None and value > maximum)):
        raise ValueError(f"{label} must be finite and in range")


def _name(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")


def _record(value, kind):
    if not isinstance(value, kind):
        raise ValueError(f"Invalid record: {value!r}")


def _records(values, kind):
    if not isinstance(values, tuple):
        raise ValueError("Record collections must be tuples")
    for value in values:
        _record(value, kind)


def _endpoints(origin, destination):
    _integer(origin, "origin_id")
    _integer(destination, "destination_id")
    if origin == destination:
        raise ValueError("Endpoints must be distinct")


@dataclass(frozen=True)
class Node:
    node_id: int
    display_name: str
    lead_time_days: float
    reliability: float

    def __post_init__(self):
        _integer(self.node_id, "node_id")
        _name(self.display_name, "display_name")
        _number(self.lead_time_days, "lead_time_days")
        object.__setattr__(self, "lead_time_days", float(self.lead_time_days))
        _number(self.reliability, "reliability", 1)
        object.__setattr__(self, "reliability", float(self.reliability))


@dataclass(frozen=True)
class Edge:
    origin_id: int
    destination_id: int
    transit_hours: float

    def __post_init__(self):
        _endpoints(self.origin_id, self.destination_id)
        _number(self.transit_hours, "transit_hours")
        object.__setattr__(self, "transit_hours", float(self.transit_hours))

    @property
    def endpoints(self) -> tuple[int, int]:
        return self.origin_id, self.destination_id


@dataclass(frozen=True)
class NetworkRef:
    network_id: str
    version: int

    def __post_init__(self):
        _name(self.network_id, "network_id")
        _integer(self.version, "version", 1)


@dataclass(frozen=True)
class NetworkSnapshot:
    ref: NetworkRef
    display_name: str
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]

    def __post_init__(self):
        _record(self.ref, NetworkRef)
        _name(self.display_name, "display_name")
        _records(self.nodes, Node)
        _records(self.edges, Edge)
        ids = {node.node_id for node in self.nodes}
        if len(ids) != len(self.nodes):
            raise ValueError("Duplicate node ID")
        if len({edge.endpoints for edge in self.edges}) != len(self.edges):
            raise ValueError("Duplicate directed route")
        if any(not ids.issuperset(edge.endpoints) for edge in self.edges):
            raise ValueError("Route endpoints must exist in the snapshot")
        object.__setattr__(self, "nodes", tuple(sorted(self.nodes, key=lambda node: node.node_id)))
        object.__setattr__(self, "edges", tuple(sorted(self.edges, key=lambda edge: edge.endpoints)))


def network_fingerprint(snapshot: NetworkSnapshot) -> str:
    """SHA-256 of the canonical snapshot, including its identity and version."""
    payload = json.dumps(asdict(snapshot), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Shipment:
    origin_id: int
    destination_id: int
    deadline_hours: float

    def __post_init__(self):
        _endpoints(self.origin_id, self.destination_id)
        _number(self.deadline_hours, "deadline_hours")
        object.__setattr__(self, "deadline_hours", float(self.deadline_hours))


@dataclass(frozen=True)
class NodeOutage:
    node_id: int

    def __post_init__(self):
        _integer(self.node_id, "node_id")


@dataclass(frozen=True)
class EdgeDelay:
    origin_id: int
    destination_id: int
    added_hours: float

    def __post_init__(self):
        _endpoints(self.origin_id, self.destination_id)
        _number(self.added_hours, "added_hours")
        object.__setattr__(self, "added_hours", float(self.added_hours))
        if not self.added_hours:
            raise ValueError("Delay must be positive")


@dataclass(frozen=True)
class RouteClosure:
    origin_id: int
    destination_id: int

    def __post_init__(self):
        _endpoints(self.origin_id, self.destination_id)


@dataclass(frozen=True)
class TransportSlowdown:
    origin_id: int
    destination_id: int
    factor: float

    def __post_init__(self):
        _endpoints(self.origin_id, self.destination_id)
        _number(self.factor, "slowdown factor")
        if self.factor < 1:
            raise ValueError("Slowdown factor must be at least 1")
        object.__setattr__(self, "factor", float(self.factor))


Disruption = Union[NodeOutage, EdgeDelay, RouteClosure, TransportSlowdown]


@dataclass(frozen=True)
class Scenario:
    disruption: Disruption
    backup_edges: tuple[Edge, ...]

    def __post_init__(self):
        _record(self.disruption, (NodeOutage, EdgeDelay, RouteClosure, TransportSlowdown))
        _records(self.backup_edges, Edge)
        if not self.backup_edges or len({edge.endpoints for edge in self.backup_edges}) != len(self.backup_edges):
            raise ValueError("Provide one or more distinct backup routes")
        object.__setattr__(self, "backup_edges", tuple(sorted(self.backup_edges, key=lambda edge: edge.endpoints)))


def validate_scenario(network: NetworkSnapshot, shipment: Shipment, scenario: Scenario) -> None:
    """Validate snapshot membership and new backup edges before routing."""
    _record(network, NetworkSnapshot)
    _record(shipment, Shipment)
    _record(scenario, Scenario)
    ids = {node.node_id for node in network.nodes}
    routes = {edge.endpoints for edge in network.edges}
    if not ids.issuperset((shipment.origin_id, shipment.destination_id)):
        raise ValueError("Shipment endpoints must exist in the snapshot")
    disruption = scenario.disruption
    if isinstance(disruption, NodeOutage):
        if disruption.node_id not in ids:
            raise ValueError("Outage node must exist in the snapshot")
    elif (disruption.origin_id, disruption.destination_id) not in routes:
        raise ValueError("Disrupted route must exist in the snapshot")
    for edge in scenario.backup_edges:
        if not ids.issuperset(edge.endpoints) or edge.endpoints in routes:
            raise ValueError("Backup must be a new route between existing nodes")


@dataclass(frozen=True)
class ScenarioPreset:
    preset_id: str
    network: NetworkRef
    shipment: Shipment
    scenario: Scenario
    sigma: float = 0.15

    def __post_init__(self):
        _number(self.sigma, "preset sigma", 1)
        _name(self.preset_id, "preset_id")
        _record(self.network, NetworkRef)
        _record(self.shipment, Shipment)
        _record(self.scenario, Scenario)


MONTE_CARLO_VERSION = "lognormal-pcg64-v1"


@dataclass(frozen=True)
class RunSettings:
    shipment: Shipment
    scenario: Scenario
    trials: int
    seed: int
    edge_jitter_fraction: float = 0.0
    algorithm_version: str = MONTE_CARLO_VERSION
    sigma: float = 0.0

    def __post_init__(self):
        _record(self.shipment, Shipment)
        _record(self.scenario, Scenario)
        _integer(self.trials, "trials", 1)
        _integer(self.seed, "seed", 0)
        _number(self.edge_jitter_fraction, "edge_jitter_fraction", 1)
        _name(self.algorithm_version, "algorithm_version")
        _number(self.sigma, "sigma", 1)


@dataclass(frozen=True)
class Delivery:
    path: Optional[tuple[int, ...]]
    transit_hours: Optional[float]
    end_to_end_hours: Optional[float]

    def __post_init__(self):
        if self.path is None and self.transit_hours is None and self.end_to_end_hours is None:
            return
        if not isinstance(self.path, tuple) or not self.path:
            raise ValueError("A delivery requires a path")
        for node_id in self.path:
            _integer(node_id, "node_id")
        _number(self.transit_hours, "transit_hours")
        object.__setattr__(self, "transit_hours", float(self.transit_hours))
        _number(self.end_to_end_hours, "end_to_end_hours")
        if self.end_to_end_hours < self.transit_hours:
            raise ValueError("End-to-end time must include transit")

    def status(self, deadline_hours: float) -> Literal["on_time", "late", "unserved"]:
        """Classify this outcome against an inclusive end-to-end deadline."""
        _number(deadline_hours, "deadline_hours")
        if self.end_to_end_hours is None:
            return "unserved"
        return "on_time" if self.end_to_end_hours <= deadline_hours else "late"


@dataclass(frozen=True)
class ConditionTrials:
    baseline: tuple[Delivery, ...]
    stressed: tuple[Delivery, ...]
    mitigated: tuple[Delivery, ...]

    def __post_init__(self):
        for values in (self.baseline, self.stressed, self.mitigated):
            _records(values, Delivery)
        if not len(self.baseline) == len(self.stressed) == len(self.mitigated) or not self.baseline:
            raise ValueError("Conditions require equal positive trial counts")


@dataclass(frozen=True)
class RiskMetrics:
    trial_count: int
    on_time_count: int
    late_count: int
    unserved_count: int
    on_time_rate: float
    late_rate: float
    unserved_rate: float
    fragility: float
    delivered_mean_hours: Optional[float]
    delivered_p95_hours: Optional[float]

    def __post_init__(self):
        _integer(self.trial_count, "trial_count", 1)
        counts = (self.on_time_count, self.late_count, self.unserved_count)
        for count in counts:
            _integer(count, "outcome count", 0)
        if sum(counts) != self.trial_count:
            raise ValueError("Outcome counts must sum to trial count")
        for rate, count in zip((self.on_time_rate, self.late_rate, self.unserved_rate), counts):
            _number(rate, "rate", 1)
            if not math.isclose(rate, count / self.trial_count, abs_tol=1e-12):
                raise ValueError("Outcome rate must match count")
        _number(self.fragility, "fragility", 100)
        if not math.isclose(self.fragility, 100 * sum(counts[1:]) / self.trial_count, abs_tol=1e-12):
            raise ValueError("Fragility must match late and unserved counts")
        for hours in (self.delivered_mean_hours, self.delivered_p95_hours):
            if self.unserved_count < self.trial_count:
                _number(hours, "delivered hours")
            elif hours is not None:
                raise ValueError("All-unserved metrics must omit delivered times")

    @property
    def delivered_count(self) -> int:
        return self.on_time_count + self.late_count


@dataclass(frozen=True)
class Criticality:
    node_id: int
    fragility_increase_points: float

    def __post_init__(self):
        _integer(self.node_id, "node_id")
        _number(self.fragility_increase_points, "fragility_increase_points", 100)


@dataclass(frozen=True)
class Comparison:
    baseline: RiskMetrics
    stressed: RiskMetrics
    mitigated: RiskMetrics
    node_criticality: tuple[Criticality, ...]

    def __post_init__(self):
        for metrics in (self.baseline, self.stressed, self.mitigated):
            _record(metrics, RiskMetrics)
        if not self.baseline.trial_count == self.stressed.trial_count == self.mitigated.trial_count:
            raise ValueError("Comparison conditions must have the same trial count")
        _records(self.node_criticality, Criticality)
        if len({item.node_id for item in self.node_criticality}) != len(self.node_criticality):
            raise ValueError("Duplicate criticality node")

    @property
    def stress_impact(self) -> float:
        """Change in on-time rate from baseline to stress, in percentage points."""
        return 100 * (self.stressed.on_time_count - self.baseline.on_time_count) / self.baseline.trial_count

    @property
    def mitigation_improvement(self) -> float:
        """Change in on-time rate from stress to mitigation, in percentage points."""
        return 100 * (self.mitigated.on_time_count - self.stressed.on_time_count) / self.stressed.trial_count


@dataclass(frozen=True)
class CriticalityReport:
    candidate_ids: tuple[int, ...]
    trial_count: int
    baseline_fragility: float
    ranking: tuple[Criticality, ...]

    def __post_init__(self):
        _integer(self.trial_count, "sensitivity trial count", 1)
        _number(self.baseline_fragility, "sensitivity baseline fragility", 100)
        _records(self.ranking, Criticality)
        if not isinstance(self.candidate_ids, tuple):
            raise ValueError("Sensitivity candidates must be a tuple")
        for node_id in self.candidate_ids:
            _integer(node_id, "sensitivity candidate")
        if sorted(self.candidate_ids) != sorted(item.node_id for item in self.ranking):
            raise ValueError("Sensitivity ranking must cover the evaluated candidates")


@dataclass(frozen=True)
class RuntimeVersions:
    python: str
    numpy: str
    pandas: str
    networkx: str


@dataclass(frozen=True)
class RunDetails:
    snapshot: NetworkSnapshot
    fingerprint: str
    preset_id: str
    created_at_utc: str
    versions: RuntimeVersions
    code_revision: Optional[str]
    code_dirty: Optional[bool]
    trials: ConditionTrials
    criticality: CriticalityReport
    comparison_seconds: float
    criticality_seconds: float

    def __post_init__(self):
        if self.fingerprint != network_fingerprint(self.snapshot):
            raise ValueError("Stored network snapshot fingerprint does not match")
        _name(self.preset_id, "preset_id")
        _name(self.created_at_utc, "creation time")
        _record(self.versions, RuntimeVersions)
        _record(self.trials, ConditionTrials)
        _record(self.criticality, CriticalityReport)
        _number(self.comparison_seconds, "comparison seconds")
        _number(self.criticality_seconds, "criticality seconds")


@dataclass(frozen=True)
class SavedRun:
    run_id: str
    network: NetworkRef
    settings: RunSettings
    result: Comparison
    details: Optional[RunDetails] = None

    def __post_init__(self):
        _name(self.run_id, "run_id")
        _record(self.network, NetworkRef)
        _record(self.settings, RunSettings)
        _record(self.result, Comparison)
        if any(metrics.trial_count != self.settings.trials for metrics in
               (self.result.baseline, self.result.stressed, self.result.mitigated)):
            raise ValueError("Metrics trial counts must match run settings")
        if self.details is not None:
            _record(self.details, RunDetails)
            if self.details.snapshot.ref != self.network:
                raise ValueError("Run snapshot must match its network reference")
            if len(self.details.trials.baseline) != self.settings.trials:
                raise ValueError("Stored trial count must match run settings")
            if self.details.criticality.ranking != self.result.node_criticality:
                raise ValueError("Stored sensitivity ranking must match comparison")
