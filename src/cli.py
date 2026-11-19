"""Command-line workflow for the local SQLite backend."""

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from src.domain import NetworkRef, SavedRun
from src.domain.fixtures import bundled_fixtures
from src.pipeline import compare_preset, replay_run
from src.scoring import FRAGILITY_LABEL
from src.storage import SQLiteRepository
from src.utils.export import CONDITIONS, EXPORT_FILES, export_run

DEFAULT_DB = Path("var/supply_chain.sqlite3")


def _network_ref(value: str) -> NetworkRef:
    match = re.fullmatch(r"(.+)-v([1-9][0-9]*)", value)
    if match is None:
        raise argparse.ArgumentTypeError("Use a versioned network key, for example demo-v1")
    name, version = match.groups()
    try:
        return NetworkRef("coastal-demo" if name == "demo" else name, int(version))
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run and inspect supply chain stress comparisons in SQLite.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"database path (default: {DEFAULT_DB})")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db", help="initialize or migrate the database")
    commands.add_parser("seed-demo", help="seed the bundled demo snapshots and presets")
    commands.add_parser("list-networks", help="list stored network versions")

    compare = commands.add_parser("compare", help="run and save a comparison")
    compare.add_argument("--network", required=True, type=_network_ref, help="versioned key, such as demo-v1")
    compare.add_argument("--preset", required=True, help="saved scenario preset, such as port-outage")
    compare.add_argument("--seed", type=int, default=42, help="nonnegative random seed (default: 42)")
    compare.add_argument("--trials", type=int, default=2000, help="1–10000 trials (default: 2000)")
    compare.add_argument("--origin", type=int, help="override the preset's origin node ID")
    compare.add_argument("--destination", type=int, help="override the preset's destination node ID")
    compare.add_argument("--deadline-hours", type=float, help="override the preset's deadline in hours")
    compare.add_argument("--sigma", type=float, help="override the preset's lognormal volatility (0–1)")

    for name, help_text in (
        ("show-run", "display a saved comparison"),
        ("replay-run", "recompute and verify a saved comparison"),
        ("export-run", "write summary.csv, trials.csv and metadata.json"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--run-id", required=True)
        if name == "export-run":
            command.add_argument("--output-dir", required=True, type=Path)
            command.add_argument("--overwrite", action="store_true", help="replace existing export files")
    return parser


def _show(run: SavedRun) -> None:
    settings = run.settings
    shipment = settings.shipment
    print(f"Run ID: {run.run_id}")
    print(f"Network: {run.network.network_id}-v{run.network.version}")
    print(f"Shipment: {shipment.origin_id} -> {shipment.destination_id}, deadline {shipment.deadline_hours:g} h")
    print(f"Settings: seed {settings.seed}, trials {settings.trials}, sigma {settings.sigma:g}, "
          f"model {settings.algorithm_version}")
    if run.details is not None:
        print(f"Preset: {run.details.preset_id}, snapshot SHA-256 {run.details.fingerprint}")
        print("Scenario: " + json.dumps(asdict(settings.scenario), allow_nan=False))
    else:
        print("Record type: legacy summary only")
    for name in CONDITIONS:
        metrics = getattr(run.result, name)
        mean = "n/a" if metrics.delivered_mean_hours is None else f"{metrics.delivered_mean_hours:.3f} h"
        p95 = "n/a" if metrics.delivered_p95_hours is None else f"{metrics.delivered_p95_hours:.3f} h"
        print(f"{name}: {metrics.on_time_count} on time ({metrics.on_time_rate:.2%}), "
              f"{metrics.late_count} late ({metrics.late_rate:.2%}), "
              f"{metrics.unserved_count} unserved ({metrics.unserved_rate:.2%}), "
              f"{metrics.delivered_count} delivered, {FRAGILITY_LABEL} {metrics.fragility:.2f}, "
              f"delivered-only mean {mean}, P95 {p95}")
    print(f"Stress impact: {run.result.stress_impact:+.2f} percentage points")
    print(f"Mitigation improvement: {run.result.mitigation_improvement:+.2f} percentage points")
    if run.details is not None:
        report = run.details.criticality
        print(f"Sensitivity: candidates {list(report.candidate_ids)}, {report.trial_count} trials, "
              f"matching baseline fragility {report.baseline_fragility:.2f}")
        print("Ranking (node ID, fragility points): " + ", ".join(
            f"{item.node_id}: {item.fragility_increase_points:+.2f}" for item in report.ranking
        ))
        print(f"Comparison runtime: {run.details.comparison_seconds:.6f} s")
        print(f"Criticality runtime: {run.details.criticality_seconds:.6f} s")


def _run(args: argparse.Namespace) -> None:
    repository = SQLiteRepository(args.db)
    if args.command == "init-db":
        repository.initialize()
        print(f"Initialized {args.db}")
        return
    if not args.db.is_file():
        raise ValueError(f"Database does not exist: {args.db}. Run init-db first.")
    if args.command == "seed-demo":
        repository.seed(bundled_fixtures())
        print("Seeded bundled networks and presets.")
    elif args.command == "list-networks":
        for ref in repository.list_networks():
            alias = f" (alias: demo-v{ref.version})" if ref.network_id == "coastal-demo" else ""
            print(f"{ref.network_id}-v{ref.version}{alias}")
    elif args.command == "compare":
        _show(compare_preset(
            repository, args.network, args.preset, seed=args.seed, trials=args.trials,
            origin=args.origin, destination=args.destination, deadline_hours=args.deadline_hours,
            sigma=args.sigma,
        ))
    elif args.command == "replay-run":
        replay = replay_run(repository, args.run_id)
        for warning in replay.warnings:
            print(f"Replay note: {warning}", file=sys.stderr)
        print(f"Replay verified: {replay.run.run_id}")
    elif args.command == "show-run":
        _show(repository.get_run(args.run_id))
    else:
        if any((args.output_dir / name).resolve() == args.db.resolve() for name in EXPORT_FILES):
            raise ValueError("Export files must not replace the database")
        export_run(repository.get_run(args.run_id), args.output_dir, overwrite=args.overwrite)
        print(f"Exported run {args.run_id} to {args.output_dir}")


def main(argv: Optional[list[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        _run(args)
    except KeyError as error:
        print(f"Error: unknown network, preset, or run ID: {error.args[0]}", file=sys.stderr)
        return 1
    except (ValueError, OSError, sqlite3.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
