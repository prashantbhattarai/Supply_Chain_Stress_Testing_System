"""Backend model and SQLite contracts tested against temporary files."""

import math
import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from src.domain import (
    Comparison, Criticality, Delivery, Edge, EdgeDelay, NetworkRef, NetworkSnapshot,
    Node, NodeOutage, RiskMetrics, RunSettings, SavedRun, Scenario, Shipment,
    validate_scenario,
)
from src.domain.fixtures import bundled_fixtures, demo_network
from src.storage import SQLiteRepository


class DomainTests(unittest.TestCase):
    def setUp(self):
        self.demo, self.tiny = bundled_fixtures()
        self.snapshot, self.preset = self.demo

    def test_fixture_shape_and_hand_calculation(self):
        self.assertEqual(len(self.snapshot.nodes), 11)
        self.assertEqual(demo_network(), self.snapshot)
        snapshot, preset = self.tiny
        by_pair = {edge.endpoints: edge.transit_hours for edge in snapshot.edges}
        self.assertEqual(preset.scenario.disruption, NodeOutage(2))
        self.assertEqual(tuple(node.lead_time_days for node in snapshot.nodes), (1, 0, 0, 0))
        self.assertEqual(24 + by_pair[1, 2] + by_pair[2, 4], 29)
        self.assertEqual(24 + by_pair[1, 3] + by_pair[3, 4], 36)
        self.assertEqual(24 + preset.scenario.backup_edges[0].transit_hours, 32)
        self.assertEqual(preset.shipment.deadline_hours, 32)

    def test_invalid_numeric_inputs(self):
        for bad in (-1, math.inf, -math.inf, math.nan, True, "2", 10**1000):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                Edge(1, 2, bad)
            with self.subTest(value=bad), self.assertRaises(ValueError):
                Node(1, "Supplier", bad, 1)
            with self.subTest(value=bad), self.assertRaises(ValueError):
                Shipment(1, 2, bad)
        for reliability in (-0.1, 1.01, math.inf, math.nan):
            with self.subTest(value=reliability), self.assertRaises(ValueError):
                Node(1, "Port", 0, reliability)
        for invalid in (True, 1.2, 2**63):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                Node(invalid, "Port", 0, 1)
        with self.assertRaises(ValueError):
            EdgeDelay(1, 2, 0)
        with self.assertRaises(ValueError):
            Edge(1, 1, 0)

    def test_duplicate_and_missing_snapshot_entities(self):
        for changes in (
            {"nodes": self.snapshot.nodes * 2},
            {"edges": self.snapshot.edges * 2},
            {"edges": (Edge(1, 99, 2),)},
        ):
            with self.subTest(changes=changes.keys()), self.assertRaises(ValueError):
                replace(self.snapshot, **changes)
        self.assertEqual(
            self.snapshot, replace(self.snapshot, nodes=self.snapshot.nodes[::-1], edges=self.snapshot.edges[::-1])
        )

    def test_invalid_scenario_references(self):
        shipment, scenario = self.preset.shipment, self.preset.scenario
        with self.assertRaises(ValueError):
            validate_scenario(self.snapshot, replace(shipment, destination_id=99), scenario)
        for invalid in (
            replace(scenario, disruption=NodeOutage(99)),
            replace(scenario, disruption=EdgeDelay(4, 3, 1)),
            replace(scenario, backup_edges=(Edge(8, 99, 2),)),
            replace(scenario, backup_edges=(self.snapshot.edges[0],)),
        ):
            with self.subTest(scenario=invalid), self.assertRaises(ValueError):
                validate_scenario(self.snapshot, shipment, invalid)
        with self.assertRaises(ValueError):
            replace(scenario, backup_edges=scenario.backup_edges * 2)

    def test_delivery_metrics_and_settings_validation(self):
        self.assertEqual(Delivery(None, None, None).end_to_end_hours, None)
        with self.assertRaises(ValueError):
            Delivery(None, None, 0)
        with self.assertRaises(ValueError):
            RunSettings(self.preset.shipment, self.preset.scenario, True, 0, 0, "test")
        all_unserved = RiskMetrics(2, 0, 0, 2, 0, 0, 1, 100, None, None)
        with self.assertRaises(ValueError):
            replace(all_unserved, delivered_mean_hours=0)
        with self.assertRaises(ValueError):
            replace(all_unserved, fragility=0)


class StorageTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "test.sqlite3"
        self.repo = SQLiteRepository(self.path)
        self.fixtures = bundled_fixtures()
        self.snapshot, self.preset = self.fixtures[0]

    def test_initialize_seed_and_reopen(self):
        self.repo.initialize()
        self.repo.initialize()
        self.repo.seed(self.fixtures)
        self.repo.seed(self.fixtures)
        reopened = SQLiteRepository(self.path)
        self.assertEqual(reopened.list_networks(), tuple(snapshot.ref for snapshot, _ in self.fixtures))
        for snapshot, preset in self.fixtures:
            self.assertEqual(reopened.get_network(snapshot.ref), snapshot)
            self.assertEqual(reopened.get_preset(snapshot.ref, preset.preset_id), preset)
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone(), (3,))
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_immutable_versions_and_preset_round_trip(self):
        self.repo.initialize()
        self.repo.save_network(self.snapshot)
        renamed = replace(self.snapshot, display_name="New name")
        with self.assertRaises(ValueError):
            self.repo.save_network(renamed)
        newer = replace(renamed, ref=replace(self.snapshot.ref, version=2))
        self.repo.save_network(newer)
        self.assertEqual(self.repo.get_network(self.snapshot.ref), self.snapshot)
        self.assertEqual(self.repo.get_network(newer.ref), newer)
        edge_delay = replace(self.preset, scenario=replace(self.preset.scenario, disruption=EdgeDelay(3, 4, 2)))
        self.repo.save_preset(edge_delay)
        self.assertEqual(self.repo.get_preset(edge_delay.network, edge_delay.preset_id), edge_delay)
        with self.assertRaises(ValueError):
            self.repo.save_preset(self.preset)

    def test_foreign_keys_scope_versions_and_networks(self):
        self.repo.initialize()
        self.repo.save_network(self.snapshot)
        local = NetworkRef("local", 1)
        local_snapshot = NetworkSnapshot(local, "Local", (Node(1, "Local origin", 0, 1),), ())
        self.repo.save_network(local_snapshot)
        other_version = NetworkRef("local", 2)
        self.repo.save_network(replace(self.snapshot, ref=other_version))
        # Only the other network and other version contain node 2.
        for missing_id in (2, 99):
            with self.subTest(node=missing_id), self.assertRaises(sqlite3.IntegrityError):
                with self.repo._connection(write=True) as (connection, _):
                    self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone(), (1,))
                    connection.execute("INSERT INTO routes VALUES (?, ?, ?, ?, ?)", ("local", 1, 1, missing_id, 2))
        self.assertEqual(self.repo.get_network(local), local_snapshot)
        with self.assertRaises(ValueError):
            self.repo.save_preset(replace(self.preset, network=local))

    def test_database_constraints_reject_duplicates_and_invalid_values(self):
        self.repo.initialize()
        self.repo.save_network(self.snapshot)
        key = (self.snapshot.ref.network_id, self.snapshot.ref.version)
        invalid_statements = (
            ("INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?)", (*key, 1, "Duplicate", 0, 1)),
            ("INSERT INTO routes VALUES (?, ?, ?, ?, ?)", (*key, 1, 3, 2)),
            ("INSERT INTO routes VALUES (?, ?, ?, ?, ?)", (*key, 1, 4, math.inf)),
            ("INSERT INTO routes VALUES (?, ?, ?, ?, ?)", (*key, 1, 4, math.nan)),
            ("INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?)", (*key, 30, "Invalid", 0, 1.2)),
        )
        for statement, params in invalid_statements:
            with self.subTest(params=params), self.assertRaises(sqlite3.IntegrityError):
                with self.repo._connection(write=True) as (connection, _):
                    connection.execute(statement, params)
        self.assertEqual(self.repo.get_network(self.snapshot.ref), self.snapshot)

    def test_seed_rolls_back_entire_batch(self):
        self.repo.initialize()
        tiny, preset = self.fixtures[1]
        invalid = replace(preset, scenario=replace(preset.scenario, disruption=NodeOutage(99)))
        with self.assertRaises(ValueError):
            self.repo.seed((self.fixtures[0], (tiny, invalid)))
        self.assertEqual(self.repo.list_networks(), ())
        with self.assertRaises(KeyError):
            self.repo.get_preset(self.preset.network, self.preset.preset_id)

    def test_migration_failure_rolls_back_ddl_and_version(self):
        with patch("src.storage.MIGRATIONS", ("001_initial.sql", "missing_migration.sql")):
            with self.assertRaises(FileNotFoundError):
                self.repo.initialize()
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone(), (0,))
            self.assertEqual(connection.execute("PRAGMA application_id").fetchone(), (0,))
            self.assertEqual(connection.execute("SELECT name FROM sqlite_master").fetchall(), [])
        self.repo.initialize()
        self.assertEqual(self.repo.list_networks(), ())

    def test_migration_preserves_version_one_presets_and_backup_edges(self):
        with patch("src.storage.MIGRATIONS", ("001_initial.sql",)):
            self.repo.initialize()
            self.repo.save_network(self.snapshot)
            key = (self.snapshot.ref.network_id, self.snapshot.ref.version)
            with self.repo._connection(write=True) as (connection, _):
                connection.executemany(
                    "INSERT INTO scenario_presets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [(*key, "legacy-outage", 1, 10, 50, 4, None, None, None),
                     (*key, "legacy-delay", 1, 10, 50, None, 3, 4, 5)],
                )
                connection.executemany(
                    "INSERT INTO scenario_backup_routes VALUES (?, ?, ?, ?, ?, ?)",
                    [(*key, preset_id, 8, 9, 10) for preset_id in ("legacy-outage", "legacy-delay")],
                )
        self.repo.initialize()
        self.assertEqual(self.repo.get_network(self.snapshot.ref), self.snapshot)
        self.assertEqual(self.repo.get_preset(self.snapshot.ref, "legacy-outage"),
                         replace(self.preset, preset_id="legacy-outage"))
        self.assertEqual(self.repo.get_preset(self.snapshot.ref, "legacy-delay"),
                         replace(self.preset, preset_id="legacy-delay",
                                 scenario=replace(self.preset.scenario, disruption=EdgeDelay(3, 4, 5))))
        with self.repo._connection() as (connection, _):
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone(), (3,))
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_foreign_database_is_preserved(self):
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("CREATE TABLE unrelated (value TEXT)")
            connection.execute("INSERT INTO unrelated VALUES (?)", ("keep me",))
        with self.assertRaises(ValueError):
            self.repo.initialize()
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute("SELECT value FROM unrelated").fetchall(), [("keep me",)])

    def test_saved_run_round_trip_and_atomicity(self):
        self.repo.initialize()
        self.repo.seed(self.fixtures)
        settings = RunSettings(self.preset.shipment, self.preset.scenario, 2, 42, 0.1, "test-v1")
        served = RiskMetrics(2, 1, 1, 0, 0.5, 0.5, 0, 50, 55, 60)
        unserved = RiskMetrics(2, 0, 0, 2, 0, 0, 1, 100, None, None)
        comparison = Comparison(served, unserved, served, (Criticality(4, 50),))
        run = SavedRun("run-1", self.snapshot.ref, settings, comparison)
        self.repo.save_run(run)
        self.repo.save_network(replace(self.snapshot, ref=replace(self.snapshot.ref, version=2)))
        self.assertEqual(SQLiteRepository(self.path).get_run(run.run_id), run)
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.save_run(run)
        with self.repo._connection(write=True) as (connection, _):
            connection.execute(
                "CREATE TRIGGER reject_result BEFORE INSERT ON run_results "
                "BEGIN SELECT RAISE(ABORT, 'Test rollback'); END"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.save_run(replace(run, run_id="run-2"))
        with self.repo._connection() as (connection, _):
            self.assertEqual(connection.execute("SELECT run_id FROM runs").fetchall(), [("run-1",)])
        with self.assertRaises(KeyError):
            self.repo.get_run("run-2")
