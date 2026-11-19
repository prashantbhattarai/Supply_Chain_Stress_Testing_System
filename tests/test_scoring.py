"""Hand-checkable delivery scores and paired node-outage sensitivity."""

import math
import sys
import unittest
from dataclasses import replace

from src.domain import ConditionTrials, Delivery, Edge, Node, RunSettings
from src.domain.fixtures import bundled_fixtures
from src.scoring import rank_node_criticality, score, score_comparison
from src.simulation.monte_carlo import sample_node_outages, simulate


def delivered(hours):
    return Delivery((1, 4), hours, hours)


UNSERVED = Delivery(None, None, None)


class DeliveryScoringTests(unittest.TestCase):
    def test_mixed_records_and_delivered_only_statistics(self):
        metrics = score((delivered(20), UNSERVED, delivered(30), delivered(10), UNSERVED), 20)
        self.assertEqual((metrics.on_time_count, metrics.late_count, metrics.unserved_count), (2, 1, 2))
        self.assertEqual((metrics.on_time_rate, metrics.late_rate, metrics.unserved_rate), (0.4, 0.2, 0.4))
        self.assertAlmostEqual(metrics.on_time_rate + metrics.late_rate + metrics.unserved_rate, 1)
        self.assertEqual(metrics.trial_count, 5)
        self.assertEqual(metrics.delivered_count, 3)
        self.assertEqual(metrics.delivered_mean_hours, 20)
        self.assertEqual(metrics.delivered_p95_hours, 29)
        self.assertEqual(metrics.fragility, 60)

    def test_uniform_outcomes_and_inclusive_deadline(self):
        cases = (
            (delivered(10), (1, 0, 0), 0, 10),
            (delivered(11), (0, 1, 0), 100, 11),
            (UNSERVED, (0, 0, 1), 100, None),
        )
        for delivery, rates, fragility, hours in cases:
            with self.subTest(delivery=delivery):
                metrics = score((delivery,) * 3, 10)
                self.assertEqual((metrics.on_time_rate, metrics.late_rate, metrics.unserved_rate), rates)
                self.assertEqual(metrics.delivered_count, 3 if hours is not None else 0)
                self.assertEqual(metrics.fragility, fragility)
                self.assertEqual(metrics.delivered_mean_hours, hours)
                self.assertEqual(metrics.delivered_p95_hours, hours)

    def test_quantile_and_mean_remain_finite_at_extreme_values(self):
        metrics = score((delivered(0), delivered(100)), 0)
        self.assertEqual(metrics.delivered_p95_hours, 95)
        self.assertEqual(metrics.delivered_mean_hours, 50)
        large = sys.float_info.max
        metrics = score((delivered(large), delivered(large)), large)
        self.assertEqual(metrics.delivered_mean_hours, large)
        self.assertEqual(metrics.delivered_p95_hours, large)

    def test_invalid_collections_and_deadlines(self):
        for records in (None, (), (UNSERVED, None), [UNSERVED], (0,)):
            with self.subTest(records=records), self.assertRaises(ValueError):
                score(records, 10)
        for deadline in (math.inf, math.nan, -1, True):
            with self.subTest(deadline=deadline), self.assertRaises(ValueError):
                score((UNSERVED,), deadline)
        with self.assertRaises(ValueError):
            score_comparison((), 10)

    def test_comparison_percentage_point_signs(self):
        base = (delivered(10), delivered(8), delivered(11), UNSERVED)
        stress = (delivered(10), delivered(15), UNSERVED, UNSERVED)
        mitigation = (delivered(6), delivered(10), delivered(8), UNSERVED)
        result = score_comparison(ConditionTrials(base, stress, mitigation), 10)
        self.assertEqual(result.stress_impact, -25)
        self.assertEqual(result.mitigation_improvement, 50)
        reversed_order = score_comparison(ConditionTrials(mitigation, mitigation, stress), 10)
        self.assertEqual(reversed_order.stress_impact, 0)
        self.assertEqual(reversed_order.mitigation_improvement, -50)


class CriticalityTests(unittest.TestCase):
    def setUp(self):
        self.network, preset = bundled_fixtures()[1]
        self.settings = RunSettings(preset.shipment, preset.scenario, 18, 56)

    def test_cut_vertex_and_irrelevant_nodes_rank_with_deterministic_ties(self):
        network = replace(
            self.network,
            nodes=self.network.nodes + (Node(5, "Isolated", 0, 1),),
            edges=(Edge(1, 3, 2), Edge(3, 4, 3)),
        )
        report = rank_node_criticality(network, self.settings, (5, 2, 3))
        self.assertEqual(report.candidate_ids, (5, 2, 3))
        self.assertEqual(report.trial_count, 18)
        self.assertEqual(report.baseline_fragility, 0)
        self.assertEqual([(item.node_id, item.fragility_increase_points) for item in report.ranking],
                         [(3, 100), (2, 0), (5, 0)])

    def test_exact_trial_prefix_and_default_candidate_limits(self):
        network, preset = bundled_fixtures()[0]
        settings = RunSettings(preset.shipment, preset.scenario, 520, 42, sigma=0.5)
        simulation = simulate(network, settings)
        paired_baseline, _ = sample_node_outages(network, settings, (4,), 500)
        self.assertEqual(paired_baseline, simulation.baseline[:500])
        report = rank_node_criticality(network, settings)
        self.assertEqual(report.candidate_ids, (2, 3, 4, 5, 6, 7, 8, 9))
        self.assertEqual(set(report.candidate_ids), {impact.node_id for impact in report.ranking})
        self.assertEqual(report.trial_count, 500)
        self.assertEqual(report.baseline_fragility,
                         score(simulation.baseline[:500], preset.shipment.deadline_hours).fragility)

    def test_invalid_candidate_selection(self):
        for candidates in ((1,), (4,), (99,), (True,), (2, 2), tuple(range(9)), [2]):
            with self.subTest(candidates=candidates), self.assertRaises(ValueError):
                rank_node_criticality(self.network, self.settings, candidates)
