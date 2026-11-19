"""Process-level CLI workflow and atomic, replayable run persistence."""

import csv
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from src.domain import NetworkRef, network_fingerprint
from src.pipeline import compare_preset, replay_run
from src.storage import SQLiteRepository


class BackendWorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.db = self.directory / "backend.sqlite3"
        self.repository = SQLiteRepository(self.db)

    def cli(self, *args, succeeds=True):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--db", str(self.db), *args],
            cwd=root, capture_output=True, text=True, timeout=20,
        )
        if succeeds:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertNotIn("Traceback", result.stderr)
        return result

    def seed(self):
        self.cli("init-db")
        self.cli("seed-demo")

    def test_end_to_end_cli_and_exports_match_stored_trials(self):
        self.seed()
        self.cli("seed-demo")
        self.assertIn("coastal-demo-v1 (alias: demo-v1)", self.cli("list-networks").stdout)
        compare = self.cli("compare", "--network", "demo-v1", "--preset", "port-outage",
                           "--seed", "42", "--trials", "32")
        run_id = compare.stdout.splitlines()[0].split(": ", 1)[1]
        self.assertIn("Comparison runtime:", compare.stdout)
        self.assertIn("Criticality runtime:", compare.stdout)
        stored = SQLiteRepository(self.db).get_run(run_id)
        self.assertEqual(stored.settings.sigma, 0.15)
        self.assertEqual(stored.details.fingerprint, network_fingerprint(stored.details.snapshot))
        self.assertEqual(stored.details.criticality.trial_count, 32)
        self.assertEqual(stored.details.criticality.candidate_ids, (2, 3, 4, 5, 6, 7, 8, 9))
        self.assertEqual(self.cli("show-run", "--run-id", run_id).stdout, compare.stdout)

        newer = replace(stored.details.snapshot, ref=NetworkRef(stored.network.network_id, 2),
                        display_name="Changed version", edges=())
        self.repository.save_network(newer)
        self.assertIn("coastal-demo-v2", self.cli("list-networks").stdout)
        self.assertEqual(self.cli("show-run", "--run-id", run_id).stdout, compare.stdout)
        self.assertIn(run_id, self.cli("replay-run", "--run-id", run_id).stdout)

        output = self.directory / "exports"
        export = ("export-run", "--run-id", run_id, "--output-dir", str(output))
        self.cli(*export)
        metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"),
                              parse_constant=lambda value: self.fail(f"Nonfinite JSON number: {value}"))
        self.assertEqual(metadata["network_fingerprint_sha256"], stored.details.fingerprint)
        self.assertEqual(metadata["settings"]["shipment"]["deadline_hours"], 50)
        self.assertEqual(metadata["criticality"]["candidate_ids"], list(stored.details.criticality.candidate_ids))
        self.assertEqual(metadata["versions"]["numpy"], stored.details.versions.numpy)
        with (output / "summary.csv").open(newline="", encoding="utf-8") as handle:
            summaries = list(csv.DictReader(handle))
        with (output / "trials.csv").open(newline="", encoding="utf-8") as handle:
            trial_rows = list(csv.DictReader(handle))
        self.assertEqual(len(summaries), 3)
        self.assertEqual(len(trial_rows), 96)
        for summary, metadata_summary in zip(summaries, metadata["summaries"]):
            condition = summary["condition"]
            expected_metrics = getattr(stored.result, condition)
            self.assertEqual(int(summary["on_time_count"]), expected_metrics.on_time_count)
            self.assertEqual(metadata_summary["unserved_count"], expected_metrics.unserved_count)
            self.assertEqual(int(summary["delivered_count"]), expected_metrics.delivered_count)
            self.assertEqual(float(summary["fragility"]), expected_metrics.fragility)
            rows = [row for row in trial_rows if row["condition"] == condition]
            for index, (row, trial) in enumerate(zip(rows, getattr(stored.details.trials, condition)), start=1):
                self.assertEqual(row["run_id"], run_id)
                self.assertEqual(int(row["trial_index"]), index)
                self.assertEqual(row["status"], trial.status(50))
                self.assertEqual(row["path_node_ids"], json.dumps(trial.path) if trial.path else "")
                self.assertEqual(row["transit_hours"], "" if trial.transit_hours is None else str(trial.transit_hours))
                self.assertEqual(row["end_to_end_hours"], "" if trial.end_to_end_hours is None
                                 else str(trial.end_to_end_hours))

        original = (output / "summary.csv").read_bytes()
        self.assertIn("already exists", self.cli(*export, succeeds=False).stderr)
        self.assertEqual((output / "summary.csv").read_bytes(), original)
        self.cli(*export, "--overwrite")

    def test_fixtures_load_from_another_working_directory(self):
        root = Path(__file__).resolve().parents[1]
        self.repository.initialize()
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--db", str(self.db), "seed-demo"],
            cwd=self.directory, env={**os.environ, "PYTHONPATH": str(root)},
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.repository.list_networks(), (NetworkRef("coastal-demo", 1), NetworkRef("tiny", 1)))

    def test_rejects_complete_run_with_mismatched_summary(self):
        self.repository.initialize()
        self.cli("seed-demo")
        run = compare_preset(self.repository, NetworkRef("tiny", 1), "port-outage", trials=3, sigma=0)
        inconsistent = replace(run, run_id="bad-summary", result=replace(
            run.result, baseline=run.result.stressed,
        ))
        with self.assertRaisesRegex(ValueError, "summaries do not match"):
            self.repository.save_run(inconsistent)
        with self.assertRaises(KeyError):
            self.repository.get_run(inconsistent.run_id)

    def test_invalid_cli_requests_have_clear_errors(self):
        self.assertIn("--db", self.cli("--help").stdout)
        self.assertIn("init-db first", self.cli("list-networks", succeeds=False).stderr)
        self.seed()
        common = ("compare", "--network", "demo-v1", "--preset", "port-outage")
        checks = (
            (("compare", "--network", "demo", "--preset", "port-outage"), "versioned network"),
            (("compare", "--network", "demo-v7", "--preset", "port-outage"), "unknown"),
            (("compare", "--network", "demo-v1", "--preset", "missing"), "unknown"),
            ((*common, "--trials", "0"), "trials"),
            ((*common, "--seed", "-1"), "seed"),
            ((*common, "--sigma", "nan"), "sigma"),
            ((*common, "--deadline-hours", "-1"), "deadline"),
            ((*common, "--destination", "100"), "Shipment endpoints"),
            (("show-run", "--run-id", "unknown"), "unknown"),
            (("replay-run", "--run-id", "unknown"), "unknown"),
        )
        for args, expected in checks:
            with self.subTest(args=args):
                self.assertIn(expected, self.cli(*args, succeeds=False).stderr)

    def test_overrides_and_distinct_run_ids(self):
        self.seed()
        ref = NetworkRef("tiny", 1)
        override = dict(seed=12, trials=3, origin=1, destination=4, deadline_hours=29, sigma=0)
        first = compare_preset(self.repository, ref, "port-outage", **override)
        second = compare_preset(self.repository, ref, "port-outage", **override)
        self.assertNotEqual(first.run_id, second.run_id)
        self.assertEqual(first.result.baseline.on_time_count, 3)
        self.assertEqual(first.result.stressed.late_count, 3)
        self.assertEqual(first.result.mitigated.late_count, 3)
        self.assertEqual(first.details.trials, second.details.trials)
        self.assertEqual(first, self.repository.get_run(first.run_id))

    def test_full_run_write_rolls_back_on_details_failure(self):
        self.seed()
        with self.repository._connection(write=True) as (connection, _):
            connection.execute(
                "CREATE TRIGGER reject_details BEFORE INSERT ON run_details "
                "BEGIN SELECT RAISE(ABORT, 'Injected write failure'); END"
            )
        with self.assertRaisesRegex(sqlite3.IntegrityError, "Injected write failure"):
            compare_preset(self.repository, NetworkRef("tiny", 1), "port-outage", trials=3)
        with self.repository._connection() as (connection, _):
            for table in ("runs", "run_results", "run_details"):
                self.assertEqual(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone(), (0,))

    def test_replay_rejects_incompatible_metadata(self):
        self.seed()
        run = compare_preset(self.repository, NetworkRef("tiny", 1), "port-outage", trials=3)
        incompatible = replace(run, run_id="other-numpy", details=replace(
            run.details, versions=replace(run.details.versions, numpy="0.1"),
        ))
        self.repository.save_run(incompatible)
        with self.assertRaisesRegex(ValueError, "numpy recorded=0.1"):
            replay_run(self.repository, incompatible.run_id)
        unsupported = replace(run, run_id="other-model", settings=replace(run.settings, algorithm_version="other"))
        self.repository.save_run(unsupported)
        with self.assertRaisesRegex(ValueError, "Incompatible model"):
            replay_run(self.repository, unsupported.run_id)

    def test_replay_uses_embedded_snapshot_and_checks_fingerprint(self):
        self.seed()
        run = compare_preset(self.repository, NetworkRef("tiny", 1), "port-outage", trials=3)
        with self.repository._connection(write=True) as (connection, _):
            connection.execute(
                "UPDATE routes SET transit_hours = ? WHERE network_id = ? AND version = ?",
                (40, "tiny", 1),
            )
        self.assertEqual(replay_run(self.repository, run.run_id).run, run)
        with self.repository._connection(write=True) as (connection, _):
            payload = json.loads(connection.execute(
                "SELECT details_json FROM run_details WHERE run_id = ?", (run.run_id,)
            ).fetchone()[0])
            payload["snapshot"]["display_name"] = "Corrupted copy"
            connection.execute("UPDATE run_details SET details_json = ? WHERE run_id = ?",
                               (json.dumps(payload), run.run_id))
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            replay_run(self.repository, run.run_id)
