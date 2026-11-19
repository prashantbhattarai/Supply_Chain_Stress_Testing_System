"""Export a complete persisted comparison as a three-file bundle."""

import csv
import json
import os
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from src.domain import SavedRun
from src.scoring import FRAGILITY_LABEL

CONDITIONS = ("baseline", "stressed", "mitigated")
EXPORT_FILES = ("summary.csv", "trials.csv", "metadata.json")


def summary_rows(run: SavedRun) -> list[dict]:
    """Expose condition metrics and their common run settings."""
    details = run.details
    return [
        {
            "run_id": run.run_id,
            "network_id": run.network.network_id,
            "network_version": run.network.version,
            "preset_id": details.preset_id if details else None,
            "condition": condition,
            "origin_id": run.settings.shipment.origin_id,
            "destination_id": run.settings.shipment.destination_id,
            "deadline_hours": run.settings.shipment.deadline_hours,
            "seed": run.settings.seed,
            "sigma": run.settings.sigma,
            **asdict(metrics),
            "delivered_count": metrics.delivered_count,
            "stress_impact_percentage_points": run.result.stress_impact,
            "mitigation_improvement_percentage_points": run.result.mitigation_improvement,
        }
        for condition in CONDITIONS
        for metrics in (getattr(run.result, condition),)
    ]


def _write_bundle(run: SavedRun, directory: Path) -> None:
    details = run.details
    if details is None:
        raise ValueError("This older run lacks trial records and cannot be exported as a complete bundle")

    summaries = summary_rows(run)
    with (directory / "summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)

    deadline = run.settings.shipment.deadline_hours
    with (directory / "trials.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("run_id", "condition", "trial_index", "status", "path_node_ids",
                         "transit_hours", "end_to_end_hours"))
        for condition in CONDITIONS:
            for index, delivery in enumerate(getattr(details.trials, condition), start=1):
                path = json.dumps(delivery.path, allow_nan=False) if delivery.path is not None else None
                writer.writerow((run.run_id, condition, index, delivery.status(deadline),
                                 path, delivery.transit_hours, delivery.end_to_end_hours))

    metadata = {key: asdict(getattr(details, key)) for key in ("snapshot", "versions", "criticality")}
    metadata.update({
        "run_id": run.run_id,
        "preset_id": details.preset_id,
        "created_at_utc": details.created_at_utc,
        "network_fingerprint_sha256": details.fingerprint,
        "code_revision": details.code_revision,
        "code_dirty": details.code_dirty,
        "comparison_seconds": details.comparison_seconds,
        "criticality_seconds": details.criticality_seconds,
        "settings": asdict(run.settings),
        "disruption_type": type(run.settings.scenario.disruption).__name__,
        "conditions": {
            "baseline": {"disruption": False, "backup": False},
            "stressed": {"disruption": True, "backup": False},
            "mitigated": {"disruption": True, "backup": True},
        },
        "units": {
            "delivery_time": "hours",
            "source_lead_time": "days",
            "outcome_rates": "fraction",
            "comparison_changes": "percentage points",
            "fragility": "0–100, " + FRAGILITY_LABEL,
            "runtime": "seconds",
        },
        "summaries": summaries,
    })
    (directory / "metadata.json").write_text(
        json.dumps(metadata, indent=2, allow_nan=False) + "\n", encoding="utf-8",
    )


def export_run(run: SavedRun, destination: Path, *, overwrite: bool = False) -> None:
    """Generate files before publishing and prevent accidental overwrite."""
    if run.details is None:
        raise ValueError("This older run lacks trial records and cannot be exported as a complete bundle")
    destination.mkdir(parents=True, exist_ok=True)
    for name in EXPORT_FILES:
        target = destination / name
        if target.is_dir() or (not overwrite and (target.exists() or target.is_symlink())):
            raise FileExistsError(f"Export destination already exists: {target}")

    with TemporaryDirectory(prefix=".export-", dir=destination) as temporary:
        staging = Path(temporary)
        _write_bundle(run, staging)
        published = []
        try:
            for name in EXPORT_FILES:
                target = destination / name
                if overwrite:
                    os.replace(staging / name, target)
                else:
                    os.link(staging / name, target)
                    published.append(target)
        except OSError:
            for target in published:
                target.unlink()
            raise
