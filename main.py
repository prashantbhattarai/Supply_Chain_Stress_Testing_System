"""Run the Phase 1 data-generation, graph, and shortest-path pipeline."""
from src.data_generation.suppliers import generate_suppliers
from src.data_generation.routes import generate_routes
from src.data_generation.merge_data import merge_supplier_routes
from src.graph.build_graph import build_graph
from src.graph.graph_analysis import shortest_path_metrics


def run_phase1(seed=42):
    """Return repeatable data, merged data, graph, and the 1-to-20 path result."""
    suppliers = generate_suppliers(20, seed=seed)
    routes = generate_routes(80, start=1, end=20, seed=seed)
    merged = merge_supplier_routes(suppliers, routes)
    graph = build_graph(routes, suppliers)
    result = shortest_path_metrics(graph, 1, 20)
    return suppliers, routes, merged, graph, result


def main():
    """Print a concise Phase 1 report without writing files."""
    suppliers, routes, merged, graph, result = run_phase1()
    print("Supply Chain Stress Tester - Phase 1")
    print(f"Suppliers: {len(suppliers)} | Routes: {len(routes)} | Merged rows: {len(merged)}")
    print(f"Directed graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
    print(f"Dijkstra status: {result.status}")
    if result.path is not None:
        print("Shortest path:", " -> ".join(map(str, result.path)))
        print(f"Total transit time: {result.total_time:g} hours")
    else:
        print(result.detail)


if __name__ == "__main__":
    main()
