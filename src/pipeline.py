"""Application service for comparing, saving, and replaying shipments."""

import os
import platform
import subprocess
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Optional
from uuid import uuid4

import networkx
import numpy
import pandas

from src.domain import (
    MONTE_CARLO_VERSION, Comparison, ConditionTrials, NetworkRef, NetworkSnapshot,
    RunDetails, RunSettings, RuntimeVersions, SavedRun, Shipment, network_fingerprint,
)
from src.scoring import rank_node_criticality, score_comparison
from src.simulation.monte_carlo import simulate
from src.storage import SQLiteRepository


@dataclass(frozen=True)
class ReplayResult:
    run: SavedRun
    warnings: tuple[str, ...]


def runtime_versions() -> RuntimeVersions:
    return RuntimeVersions(platform.python_version(), numpy.__version__, pandas.__version__, networkx.__version__)


def code_state() -> tuple[Optional[str], Optional[bool]]:
    root = Path(__file__).resolve().parents[1]

    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(root), *args], text=True, stderr=subprocess.DEVNULL,
            timeout=3, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        ).strip()

    try:
        revision = git("rev-parse", "HEAD")
    except (OSError, subprocess.SubprocessError):
        return None, None
    try:
        return revision, bool(git("status", "--porcelain"))
    except (OSError, subprocess.SubprocessError):
        return revision, None


def _evaluate(network: NetworkSnapshot, settings: RunSettings):
    start = perf_counter()
    simulation = simulate(network, settings)
    metrics = score_comparison(simulation, settings.shipment.deadline_hours)
    comparison_seconds = perf_counter() - start

    start = perf_counter()
    criticality = rank_node_criticality(network, settings)
    criticality_seconds = perf_counter() - start
    return (
        ConditionTrials(simulation.baseline, simulation.stressed, simulation.mitigated),
        replace(metrics, node_criticality=criticality.ranking), criticality,
        comparison_seconds, criticality_seconds,
    )


def compare(network: NetworkSnapshot, settings: RunSettings) -> Comparison:
    """Compute a typed comparison without saving or printing."""
    return _evaluate(network, settings)[1]


def compare_and_save(
    repository: SQLiteRepository, ref: NetworkRef, settings: RunSettings, *, preset_id: str = "custom",
) -> SavedRun:
    """Run and atomically persist a complete comparison for a saved network."""
    network = repository.get_network(ref)
    revision, dirty = code_state()
    trials, result, criticality, comparison_seconds, criticality_seconds = _evaluate(network, settings)
    details = RunDetails(
        network, network_fingerprint(network), preset_id, datetime.now(timezone.utc).isoformat(),
        runtime_versions(), revision, dirty, trials, criticality, comparison_seconds, criticality_seconds,
    )
    run = SavedRun(str(uuid4()), ref, settings, result, details)
    repository.save_run(run)
    return run


def compare_preset(
    repository: SQLiteRepository, ref: NetworkRef, preset_id: str, *, seed: int = 42,
    trials: int = 2000, origin: Optional[int] = None, destination: Optional[int] = None,
    deadline_hours: Optional[float] = None, sigma: Optional[float] = None,
) -> SavedRun:
    """Resolve the saved preset and apply explicit shipment or volatility overrides."""
    preset = repository.get_preset(ref, preset_id)
    shipment = Shipment(
        preset.shipment.origin_id if origin is None else origin,
        preset.shipment.destination_id if destination is None else destination,
        preset.shipment.deadline_hours if deadline_hours is None else deadline_hours,
    )
    settings = RunSettings(shipment, preset.scenario, trials, seed, sigma=preset.sigma if sigma is None else sigma)
    return compare_and_save(repository, ref, settings, preset_id=preset_id)


def replay_run(repository: SQLiteRepository, run_id: str) -> ReplayResult:
    """Recompute and verify saved output from the embedded snapshot and settings."""
    run = repository.get_run(run_id)
    details = run.details
    if details is None:
        raise ValueError("This older run has only summaries and cannot be replayed")
    if run.settings.algorithm_version != MONTE_CARLO_VERSION:
        raise ValueError(f"Incompatible model version: {run.settings.algorithm_version}")
    current = runtime_versions()
    mismatches = [
        f"{key} recorded={value}, current={getattr(current, key)}"
        for key, value in vars(details.versions).items()
        if value != getattr(current, key)
    ]
    if mismatches:
        raise ValueError("Incompatible replay environment: " + "; ".join(mismatches))

    revision, dirty = code_state()
    warnings = []
    if revision is None or details.code_revision is None:
        warnings.append("Code revision is unavailable for the original run or replay.")
    elif revision != details.code_revision:
        warnings.append(f"Code revision differs (recorded {details.code_revision}, current {revision}).")
    if dirty is not False or details.code_dirty is not False:
        warnings.append("The original or replay worktree was dirty or its state could not be verified.")

    trials, result, criticality, _, _ = _evaluate(details.snapshot, run.settings)
    if (trials, result, criticality) != (details.trials, run.result, details.criticality):
        raise ValueError("Replay differed from stored trials, metrics, or sensitivity results")
    return ReplayResult(run, tuple(warnings))
