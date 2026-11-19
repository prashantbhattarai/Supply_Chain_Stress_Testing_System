"""Delivery metrics and measured transit-node sensitivity."""

from dataclasses import dataclass
from statistics import mean
from typing import Optional

import numpy as np

from src.domain import Comparison, ConditionTrials, Criticality, Delivery, NetworkSnapshot, RiskMetrics, RunSettings
from src.simulation.monte_carlo import (
    MAX_SENSITIVITY_CANDIDATES, MAX_SENSITIVITY_TRIALS, sample_node_outages,
)

FRAGILITY_LABEL = "Fragility (defined deadline-risk score)"


def score(deliveries: tuple[Delivery, ...], deadline_hours: float) -> RiskMetrics:
    """Score trial records using an inclusive deadline and delivered-only times."""
    if not isinstance(deliveries, tuple) or not deliveries or any(
        not isinstance(delivery, Delivery) for delivery in deliveries
    ):
        raise ValueError("Expected a nonempty tuple of Delivery records")

    counts = {"on_time": 0, "late": 0, "unserved": 0}
    delivered_hours = []
    for delivery in deliveries:
        counts[delivery.status(deadline_hours)] += 1
        if delivery.end_to_end_hours is not None:
            delivered_hours.append(delivery.end_to_end_hours)

    total = len(deliveries)
    on_time, late, unserved = counts["on_time"], counts["late"], counts["unserved"]
    return RiskMetrics(
        trial_count=total,
        on_time_count=on_time,
        late_count=late,
        unserved_count=unserved,
        on_time_rate=on_time / total,
        late_rate=late / total,
        unserved_rate=unserved / total,
        fragility=100 * (late + unserved) / total,
        delivered_mean_hours=float(mean(delivered_hours)) if delivered_hours else None,
        delivered_p95_hours=(
            float(np.percentile(np.asarray(delivered_hours, dtype=float), 95, method="linear"))
            if delivered_hours else None
        ),
    )


def score_comparison(trials: ConditionTrials, deadline_hours: float) -> Comparison:
    """Score three aligned conditions against the same deadline."""
    if not isinstance(trials, ConditionTrials):
        raise ValueError("Expected aligned ConditionTrials")
    return Comparison(
        score(trials.baseline, deadline_hours),
        score(trials.stressed, deadline_hours),
        score(trials.mitigated, deadline_hours),
        (),
    )


@dataclass(frozen=True)
class CriticalityReport:
    candidate_ids: tuple[int, ...]
    trial_count: int
    baseline_fragility: float
    ranking: tuple[Criticality, ...]


def rank_node_criticality(
    network: NetworkSnapshot, settings: RunSettings, candidate_ids: Optional[tuple[int, ...]] = None,
) -> CriticalityReport:
    """Rank selected transit nodes using a shared prefix of baseline trials."""
    if not isinstance(network, NetworkSnapshot) or not isinstance(settings, RunSettings):
        raise ValueError("A validated network snapshot and run settings are required")

    if candidate_ids is None:
        shipment = settings.shipment
        transit_ids = tuple(
            node.node_id for node in network.nodes
            if node.node_id not in (shipment.origin_id, shipment.destination_id)
        )
        candidate_ids = transit_ids[:MAX_SENSITIVITY_CANDIDATES]

    trial_count = min(settings.trials, MAX_SENSITIVITY_TRIALS)
    baseline, outages = sample_node_outages(network, settings, candidate_ids, trial_count)
    deadline = settings.shipment.deadline_hours
    baseline_metrics = score(baseline, deadline)
    ranking = []
    for node_id, deliveries in outages.items():
        metrics = score(deliveries, deadline)
        # Paired trials use the same denominator. Use integer differences to preserve ties.
        increase = 100 * (baseline_metrics.on_time_count - metrics.on_time_count) / trial_count
        ranking.append(Criticality(node_id, increase))
    ranking.sort(key=lambda impact: (-impact.fragility_increase_points, impact.node_id))
    return CriticalityReport(candidate_ids, trial_count, baseline_metrics.fragility, tuple(ranking))
