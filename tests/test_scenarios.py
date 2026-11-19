"""Deterministic routing across disruptions and versioned SQLite snapshots."""

import math
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from src.domain import (
    Comparison, Delivery, Edge, EdgeDelay, Node, NodeOutage, RiskMetrics,
    RouteClosure, RunSettings, SavedRun, Scenario, Shipment, TransportSlowdown,
)
from src.domain.fixtures import bundled_fixtures
from src.graph.scenarios import apply_disruption, build_snapshot_graph, deterministic
from src.storage import SQLiteRepository


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.network, self.preset = bundled_fixtures()[1]
        self.shipment = self.preset.shipment

    def run_scenario(self, disruption, backup=None):
        backup = self.preset.scenario.backup_edges if backup is None else backup
        return deterministic(self.network, self.shipment, Scenario(disruption, backup))

    def test_day_hour_conversion_and_deadline_equality(self):
        nodes = tuple(replace(node, lead_time_days=7) if node.node_id != 1 else node
                      for node in self.network.nodes)
        snapshot = replace(self.network, nodes=nodes)
        result = deterministic(snapshot, self.shipment, self.preset.scenario)
        self.assertEqual(result.baseline, (Delivery((1, 2, 4), 5, 29),))
        self.assertEqual(result.stressed, (Delivery((1, 3, 4), 12, 36),))
        self.assertEqual(result.mitigated, (Delivery((1, 4), 8, 32),))
        self.assertEqual(
            [items[0].status(self.shipment.deadline_hours)
             for items in (result.baseline, result.stressed, result.mitigated)],
            ["on_time", "late", "on_time"],
        )

    def test_snapshot_adapter_preserves_isolates_direction_and_metadata(self):
        snapshot = replace(self.network, nodes=self.network.nodes + (Node(5, "Isolate", 0, 1),))
        graph = build_snapshot_graph(snapshot)
        self.assertTrue(graph.is_directed())
        self.assertEqual(graph.degree(5), 0)
        self.assertEqual(graph.nodes[5]["display_name"], "Isolate")
        self.assertFalse(graph.has_edge(4, 2))
        reverse = deterministic(
            snapshot, Shipment(4, 1, 24), Scenario(NodeOutage(2), (Edge(4, 1, 2),)),
        )
        self.assertIsNone(reverse.baseline[0].path)
        self.assertIsNone(reverse.stressed[0].path)
        self.assertEqual(reverse.mitigated[0], Delivery((4, 1), 2, 2))

    def test_closure_removes_selected_direction_and_mitigation_preserves_it(self):
        self.network = replace(self.network, edges=self.network.edges + (Edge(2, 1, 1),))
        graph = build_snapshot_graph(self.network)
        closure = RouteClosure(1, 2)
        stressed = apply_disruption(graph, closure)
        self.assertFalse(stressed.has_edge(1, 2))
        self.assertTrue(stressed.has_edge(2, 1))
        self.assertTrue(graph.has_edge(1, 2))
        result = self.run_scenario(closure)
        self.assertEqual(result.stressed[0].path, (1, 3, 4))
        self.assertEqual(result.mitigated[0].path, (1, 4))
        with self.assertRaisesRegex(ValueError, "new route"):
            self.run_scenario(closure, (Edge(1, 2, 0),))

    def test_slowdown_and_legacy_delay(self):
        original = build_snapshot_graph(self.network)
        no_op = self.run_scenario(TransportSlowdown(1, 2, 1))
        self.assertEqual(no_op.baseline, no_op.stressed)
        self.assertEqual(no_op.mitigated, no_op.baseline)  # Slower backup remains valid.
        slowed = apply_disruption(original, TransportSlowdown(1, 2, 5))
        self.assertEqual(original[1][2]["time"], 2)
        self.assertEqual(slowed[1][2]["time"], 10)
        self.assertEqual(self.run_scenario(TransportSlowdown(1, 2, 5)).stressed[0].path, (1, 3, 4))
        self.assertEqual(self.run_scenario(EdgeDelay(1, 2, 9)).stressed[0].path, (1, 3, 4))

    def test_endpoint_outages_stay_unserved_even_with_incident_backup(self):
        for node_id in (self.shipment.origin_id, self.shipment.destination_id):
            with self.subTest(node_id=node_id):
                result = self.run_scenario(NodeOutage(node_id))
                self.assertEqual(result.baseline[0].status(32), "on_time")
                for delivery in (result.stressed[0], result.mitigated[0]):
                    self.assertEqual(delivery, Delivery(None, None, None))
                    self.assertEqual(delivery.status(32), "unserved")

    def test_backup_ignores_failed_transit_node(self):
        result = self.run_scenario(NodeOutage(2), (Edge(1, 4, 8), Edge(3, 2, 0)))
        self.assertEqual(result.mitigated[0], Delivery((1, 4), 8, 32))
        self.assertEqual(result.stressed[0].path, (1, 3, 4))
        with self.assertRaisesRegex(ValueError, "add a shipment path"):
            self.run_scenario(NodeOutage(2), (Edge(3, 2, 0),))

    def test_disconnection_and_multiedge_backup(self):
        self.network = replace(self.network, edges=(Edge(1, 2, 2), Edge(2, 4, 3)))
        result = self.run_scenario(RouteClosure(2, 4), (Edge(1, 3, 6), Edge(3, 4, 1)))
        self.assertEqual(result.stressed, (Delivery(None, None, None),))
        self.assertEqual(result.mitigated, (Delivery((1, 3, 4), 7, 31),))

    def test_invalid_settings_and_unused_backup(self):
        for factor in (0, 0.9, math.inf, math.nan, True, "2"):
            with self.subTest(factor=factor), self.assertRaises(ValueError):
                TransportSlowdown(1, 2, factor)
        for disruption in (RouteClosure(2, 1), TransportSlowdown(3, 2, 1), NodeOutage(99)):
            with self.subTest(disruption=disruption), self.assertRaises(ValueError):
                self.run_scenario(disruption)
        with self.assertRaisesRegex(ValueError, "remain finite"):
            self.run_scenario(TransportSlowdown(1, 2, 1.7e308))
        with self.assertRaisesRegex(ValueError, "Shipment endpoints"):
            deterministic(self.network, Shipment(1, 99, 32), self.preset.scenario)
        with self.assertRaisesRegex(ValueError, "add a shipment path"):
            self.run_scenario(TransportSlowdown(1, 2, 1), (Edge(2, 1, 1),))

    def test_routing_snapshot_from_sqlite_and_round_tripping_new_shocks(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteRepository(Path(directory) / "scenarios.sqlite3")
            repository.initialize()
            repository.seed(bundled_fixtures())
            loaded = repository.get_network(self.network.ref)
            self.assertEqual(
                deterministic(loaded, self.shipment, self.preset.scenario).mitigated[0].end_to_end_hours, 32,
            )
            metrics = RiskMetrics(1, 1, 0, 0, 1, 0, 0, 0, 32, 32)
            comparison = Comparison(metrics, metrics, metrics, ())
            cases = (RouteClosure(1, 2), TransportSlowdown(1, 2, 2))
            for index, disruption in enumerate(cases):
                scenario = replace(self.preset.scenario, disruption=disruption)
                preset = replace(self.preset, preset_id=f"preset-{index}", scenario=scenario)
                repository.save_preset(preset)
                self.assertEqual(repository.get_preset(loaded.ref, preset.preset_id), preset)
                run = SavedRun(preset.preset_id, loaded.ref, RunSettings(self.shipment, scenario, 1, 0, 0, "test"),
                               comparison)
                repository.save_run(run)
                self.assertEqual(repository.get_run(run.run_id), run)
            self.assertEqual(repository.get_network(loaded.ref), self.network)
