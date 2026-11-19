"""Reproducible, aligned trial samples and delivery outcomes."""

import math
import unittest
from dataclasses import replace
from unittest.mock import patch

import numpy as np

from src.domain import Delivery, Edge, Node, NodeOutage, RouteClosure, RunSettings, TransportSlowdown
from src.domain.fixtures import bundled_fixtures
from src.graph.scenarios import deterministic, prepare_scenario
from src.simulation import monte_carlo
from src.simulation.monte_carlo import simulate


class MonteCarloTests(unittest.TestCase):
    def setUp(self):
        self.network, preset = bundled_fixtures()[1]
        self.settings = RunSettings(preset.shipment, preset.scenario, trials=16, seed=42)

    def test_deterministic_agreement_and_deadline_equality(self):
        expected = deterministic(self.network, self.settings.shipment, self.settings.scenario)
        result = simulate(self.network, self.settings)
        for condition, status in (("baseline", "on_time"), ("stressed", "late"), ("mitigated", "on_time")):
            self.assertEqual(getattr(result, condition), getattr(expected, condition) * self.settings.trials)
            self.assertEqual(result.statuses[condition], (status,) * self.settings.trials)
        self.assertEqual(result.mitigated[0].end_to_end_hours, self.settings.shipment.deadline_hours)
        self.assertEqual(result.metadata.network, self.network.ref)
        self.assertEqual(result.metadata.settings, self.settings)
        self.assertEqual(result.metadata.numpy_version, np.__version__)

    def test_reliability_zero_one_and_complete_disconnection(self):
        for unavailable in (1, 4):
            nodes = tuple(replace(node, reliability=0) if node.node_id == unavailable else node
                          for node in self.network.nodes)
            result = simulate(replace(self.network, nodes=nodes), self.settings)
            for condition in ("baseline", "stressed", "mitigated"):
                with self.subTest(node=unavailable, condition=condition):
                    self.assertEqual(getattr(result, condition), (Delivery(None, None, None),) * self.settings.trials)
                    self.assertEqual(result.statuses[condition], ("unserved",) * self.settings.trials)

        endpoint_outage = replace(
            self.settings, scenario=replace(self.settings.scenario, disruption=NodeOutage(1)),
        )
        result = simulate(self.network, endpoint_outage)
        self.assertTrue(all(delivery.path for delivery in result.baseline))
        self.assertEqual(result.statuses["mitigated"], ("unserved",) * self.settings.trials)

        snapshot = replace(self.network, edges=(Edge(1, 2, 2), Edge(2, 4, 3)))
        settings = replace(self.settings, scenario=replace(self.settings.scenario, disruption=RouteClosure(2, 4)))
        result = simulate(snapshot, settings)
        self.assertEqual(result.stressed[0], Delivery(None, None, None))
        self.assertEqual(result.mitigated[0], Delivery((1, 4), 8, 32))

    def test_background_failure_can_already_remove_disrupted_route(self):
        nodes = tuple(replace(node, reliability=0) if node.node_id == 2 else node for node in self.network.nodes)
        settings = replace(self.settings, scenario=replace(self.settings.scenario, disruption=RouteClosure(2, 4)))
        result = simulate(replace(self.network, nodes=nodes), settings)
        self.assertEqual(result.baseline, result.stressed)
        self.assertEqual(result.stressed[0].path, (1, 3, 4))

    def test_same_seed_and_global_random_state(self):
        settings = replace(self.settings, sigma=0.7)
        global_state = np.random.get_state()
        first = simulate(self.network, settings)
        self.assertEqual(first, simulate(self.network, settings))
        different = simulate(self.network, replace(settings, seed=43))
        self.assertNotEqual(first.baseline, different.baseline)
        after = np.random.get_state()
        self.assertEqual(global_state[0], after[0])
        np.testing.assert_array_equal(global_state[1], after[1])
        self.assertEqual(global_state[2:], after[2:])

    def test_sampling_formula_for_directed_routes(self):
        settings = replace(self.settings, sigma=0.6)
        samples = monte_carlo._samples(self.network, settings)
        seed_words = np.random.default_rng(settings.seed).integers(0, 2**32, size=4, dtype=np.uint32).tolist()
        # (1, 2) uses the edge namespace and two little-endian words per signed ID.
        z = np.random.default_rng([*seed_words, 1, 1, 2**31, 2, 2**31]).standard_normal(settings.trials)
        expected = 2 * np.exp(settings.sigma * z - settings.sigma**2 / 2)
        np.testing.assert_array_equal(samples.transport_hours[1, 2], expected)

    def test_entity_draws_survive_node_removal_and_backup_change(self):
        settings = replace(self.settings, sigma=0.7)
        snapshot = replace(self.network, nodes=tuple(replace(node, reliability=0.5) for node in self.network.nodes))
        samples = monte_carlo._samples(snapshot, settings)
        removed = replace(snapshot, nodes=tuple(node for node in snapshot.nodes if node.node_id != 2),
                          edges=tuple(edge for edge in snapshot.edges if 2 not in edge.endpoints))
        retained = monte_carlo._samples(removed, settings)
        for node, draws in retained.availability.items():
            np.testing.assert_array_equal(draws, samples.availability[node])
        for edge, draws in retained.transport_hours.items():
            np.testing.assert_array_equal(draws, samples.transport_hours[edge])

        changed = replace(settings, scenario=replace(settings.scenario, backup_edges=(Edge(1, 4, 8), Edge(3, 2, 1))))
        expanded = monte_carlo._samples(snapshot, changed)
        for edge, draws in samples.transport_hours.items():
            np.testing.assert_array_equal(draws, expanded.transport_hours[edge])

    def test_evaluation_and_graph_insertion_order_independence(self):
        settings = replace(self.settings, sigma=0.5)
        expected = simulate(self.network, settings)
        baseline, stressed, mitigated = prepare_scenario(self.network, settings.shipment, settings.scenario)
        reversed_baseline = type(baseline)()
        reversed_baseline.add_nodes_from(reversed(list(baseline.nodes(data=True))))
        reversed_baseline.add_edges_from(reversed(list(baseline.edges(data=True))))
        original = monte_carlo._trial_graphs

        def reverse_conditions(*args):
            return dict(reversed(tuple(original(*args).items())))

        with patch.object(monte_carlo, "_trial_graphs", side_effect=reverse_conditions), patch.object(
            monte_carlo, "prepare_scenario", return_value=(reversed_baseline, stressed, mitigated),
        ):
            self.assertEqual(simulate(self.network, settings), expected)
        reordered = replace(self.network, nodes=self.network.nodes[::-1], edges=self.network.edges[::-1])
        self.assertEqual(simulate(reordered, settings), expected)

    def test_no_stress_and_backup_cannot_worsen_delivery(self):
        nodes = tuple(replace(node, reliability=0.55) if node.node_id in (2, 3) else node
                      for node in self.network.nodes)
        settings = replace(
            self.settings, trials=64, sigma=0.6,
            scenario=replace(self.settings.scenario, disruption=TransportSlowdown(1, 2, 1)),
        )
        result = simulate(replace(self.network, nodes=nodes), settings)
        self.assertEqual(result.baseline, result.stressed)
        self.assertTrue(any(delivery.path is None for delivery in result.stressed))
        self.assertTrue(all(delivery.path is not None for delivery in result.mitigated))
        for stressed, mitigated in zip(result.stressed, result.mitigated):
            if stressed.path is not None:
                self.assertLessEqual(mitigated.end_to_end_hours, stressed.end_to_end_hours)

    def test_validation_before_samples(self):
        all_nodes = tuple(Node(i, f"Node {i}", 0, 1) for i in range(1, 27))
        oversized_network = replace(self.network, nodes=all_nodes)
        edges = tuple(Edge(a, b, 1) for a in range(1, 10) for b in range(1, 10)
                      if a != b and (a, b) != (1, 4))
        oversized_edges = replace(self.network, nodes=all_nodes[:9], edges=edges)
        for network, settings in (
            (None, self.settings),
            (self.network, None),
            (oversized_network, self.settings),
            (oversized_edges, self.settings),
            (self.network, replace(self.settings, trials=10_001)),
            (self.network, replace(self.settings, algorithm_version="unknown")),
            (self.network, replace(self.settings, edge_jitter_fraction=0.2)),
            (self.network, replace(self.settings, shipment=replace(self.settings.shipment, destination_id=99))),
        ):
            with self.subTest(settings=settings), patch.object(monte_carlo.np.random, "default_rng") as rng:
                with self.assertRaises(ValueError):
                    simulate(network, settings)
                rng.assert_not_called()

    def test_invalid_setting_values(self):
        for field, values in (
            ("trials", (0, -1, True, 1.5)),
            ("seed", (-1, False, 1.5)),
            ("sigma", (-0.1, 1.01, math.nan, math.inf, True)),
        ):
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    replace(self.settings, **{field: value})
        for value in (-1, True, math.inf, math.nan):
            with self.subTest(deadline=value), self.assertRaises(ValueError):
                replace(self.settings.shipment, deadline_hours=value)
