"""Behavior tests for the Phase 1 pipeline; run with unittest discovery."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import networkx as nx
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from main import run_phase1
from src.cleaning.cleaning import clean_suppliers
from src.data_generation.suppliers import generate_suppliers
from src.data_generation.routes import generate_routes
from src.data_generation.routes_io import read_routes_csv_bytes
from src.data_generation.merge_data import merge_supplier_routes
from src.graph.build_graph import build_graph
from src.graph.graph_analysis import shortest_path_metrics
from src.utils.file_loader import load_csv, load_json


class GenerationTests(unittest.TestCase):
    def test_suppliers_repeatable_and_valid(self):
        data = generate_suppliers(20, seed=7)
        assert_frame_equal(data, generate_suppliers(20, seed=7))
        self.assertEqual(data.supplier_id.tolist(), list(range(1, 21)))
        self.assertTrue(data.lead_time.between(5, 39).all())
        self.assertTrue(data.reliability.between(0.8, 0.99).all())

    def test_global_random_state_unchanged(self):
        np.random.seed(12)
        expected = np.random.random(3)
        np.random.seed(12)
        generate_suppliers(5, seed=42)
        generate_routes(5, seed=42)
        np.testing.assert_array_equal(np.random.random(3), expected)

    def test_route_bounds_direction_and_repeatability(self):
        data = generate_routes(100, start=30, end=35, seed=7)
        assert_frame_equal(data, generate_routes(100, start=30, end=35, seed=7))
        self.assertTrue(data.origin.between(30, 35).all())
        self.assertTrue(data.destination.between(30, 35).all())
        self.assertTrue((data.origin != data.destination).all())
        self.assertEqual(tuple(data.loc[0, ['origin', 'destination']]), (30, 35))
        self.assertTrue(data.time.between(2, 14).all())
        self.assertTrue(data.route_id.is_unique)

    def test_empty_generation(self):
        self.assertEqual(generate_routes(0).shape, (0, 4))
        self.assertEqual(generate_suppliers(0).shape, (0, 3))

    def test_invalid_arguments(self):
        for value in [-1, 1.5, True]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError): generate_routes(value)
                with self.assertRaises(ValueError): generate_suppliers(value)
        for start, end in [(2, 2), (4, 1), (1.5, 3), (True, 3)]:
            with self.assertRaises(ValueError): generate_routes(start=start, end=end)

    def test_cleaning_copy_and_validation(self):
        raw = pd.DataFrame({' Supplier ID ': [1], 'Lead Time': ['5'], 'Reliability': ['0.9']})
        self.assertEqual(clean_suppliers(raw).lead_time.iloc[0], 5.0)
        self.assertIn('Lead Time', raw.columns)
        for column, value in [('lead_time', -1), ('reliability', 2), ('lead_time', float('inf')), ('supplier_id', None)]:
            invalid = generate_suppliers(1, seed=1)
            invalid.loc[0, column] = value
            with self.assertRaises(ValueError): clean_suppliers(invalid)
        with self.assertRaises(ValueError): clean_suppliers(pd.DataFrame())
        with self.assertRaises(ValueError): clean_suppliers(pd.concat([generate_suppliers(1)] * 2))


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.routes = pd.DataFrame({'origin': [1, 1, 2, 1], 'destination': [3, 2, 3, 2], 'time': [12, 8, 3, 2]})

    def test_directed_graph_duplicate_minimum_and_isolates(self):
        graph = build_graph(self.routes, generate_suppliers(4, seed=1))
        self.assertIsInstance(graph, nx.DiGraph)
        self.assertFalse(graph.has_edge(3, 1))
        self.assertEqual(graph[1][2]['time'], 2)
        self.assertEqual(graph.degree(4), 0)
        self.assertIn('reliability', graph.nodes[1])
        reversed_graph = build_graph(self.routes.iloc[::-1])
        self.assertEqual(dict(graph[1][2]), dict(reversed_graph[1][2]))
        self.assertTrue(all(isinstance(node, int) for node in graph))

    def test_dijkstra_uses_weights(self):
        graph = build_graph(self.routes)
        result = shortest_path_metrics(graph, 1, 3)
        self.assertEqual(result.path, (1, 2, 3))
        self.assertEqual(result.total_time, 5)
        self.assertTrue(result.is_connected)
        self.assertEqual(shortest_path_metrics(graph, 3, 1).status, 'no_path')

    def test_path_edge_cases(self):
        graph = build_graph(self.routes)
        for source, target, status in [(8, 3, 'missing_source'), (1, 8, 'missing_target'), (1, 1, 'same_node')]:
            self.assertEqual(shortest_path_metrics(graph, source, target).status, status)
        same = shortest_path_metrics(graph, 1, 1)
        self.assertTrue(same.is_connected)
        self.assertEqual(same.total_time, 0)
        self.assertEqual(shortest_path_metrics(nx.DiGraph(), 1, 3).status, 'empty_graph')

    def test_invalid_weights_rejected(self):
        for value in [-1, float('inf'), float('nan'), None]:
            graph = nx.DiGraph()
            graph.add_edge(1, 2, time=value)
            with self.assertRaises(ValueError): shortest_path_metrics(graph, 1, 2)
        with self.assertRaises(ValueError): shortest_path_metrics(nx.Graph(), 1, 2)

    def test_normalization_and_invalid_rows(self):
        routes = read_routes_csv_bytes(b'from,to,duration\n1,2,4\n2,3,-1\n3,4,inf\n4,5,bad\n,6,2\n')
        self.assertEqual(len(routes), 1)
        self.assertEqual(build_graph(routes).number_of_edges(), 1)
        self.assertEqual(build_graph(None).number_of_nodes(), 0)
        with self.assertRaises(ValueError): build_graph(pd.DataFrame({'wrong': [1]}))
        with self.assertRaises(ValueError): build_graph(self.routes, generate_suppliers(2))


class IntegrationTests(unittest.TestCase):
    def test_pipeline(self):
        suppliers, routes, merged, graph, result = run_phase1()
        self.assertEqual(set(graph), set(suppliers.supplier_id))
        self.assertTrue(set(routes.origin) <= set(suppliers.supplier_id))
        self.assertTrue(set(routes.destination) <= set(suppliers.supplier_id))
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.total_time, sum(graph[a][b]['time'] for a, b in zip(result.path, result.path[1:])))
        self.assertTrue(set(suppliers.supplier_id) <= set(merged.supplier_id))

    def test_merge_preserves_supplier_without_route(self):
        merged = merge_supplier_routes(generate_suppliers(4), generate_routes(1, end=2))
        self.assertEqual(set(merged.supplier_id), {1, 2, 3, 4})
        self.assertTrue(merged.loc[merged.supplier_id == 4, 'origin'].isna().all())

    def test_loaders(self):
        with tempfile.TemporaryDirectory() as folder:
            csv_path = Path(folder) / 'input.csv'
            csv_path.write_text('name,value\nalpha,2\n', encoding='utf-8')
            self.assertEqual(load_csv(csv_path), [{'name': 'alpha', 'value': '2'}])
            json_path = Path(folder) / 'input.json'
            json_path.write_text(json.dumps({'value': 2}), encoding='utf-8')
            self.assertEqual(load_json(json_path), {'value': 2})

    def test_compatibility_imports(self):
        from src.graph.builld_graph import build_graph as old_build
        from src.cleaning.simulation import clean_suppliers as old_clean
        self.assertIs(old_build, build_graph)
        self.assertIs(old_clean, clean_suppliers)

    def test_main_from_other_directory(self):
        entry = Path(__file__).resolve().parents[1] / 'main.py'
        result = subprocess.run([sys.executable, str(entry)], cwd=tempfile.gettempdir(), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Dijkstra status: ok', result.stdout)

    def test_core_imports_are_quiet(self):
        result = subprocess.run([sys.executable, '-c', 'import main; import src.cleaning.simulation; import src.data_generation.merge_data'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
