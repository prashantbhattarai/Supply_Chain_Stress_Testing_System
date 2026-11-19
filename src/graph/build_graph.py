"""Build one consistent directed graph weighted by transit hours."""
import networkx as nx

from src.data_generation.routes_io import normalize_routes_dataframe


def build_graph(routes_df, suppliers_df=None):
    """Build a DiGraph; retain the fastest edge for each ordered pair.

    Optional supplier data adds node attributes and preserves isolated suppliers.
    Unknown route endpoints are rejected when a supplier table is provided.
    """
    graph = nx.DiGraph()
    if suppliers_df is not None:
        from src.cleaning.cleaning import clean_suppliers
        for supplier in clean_suppliers(suppliers_df).to_dict("records"):
            node = supplier.pop("supplier_id")
            graph.add_node(node, **supplier)
    routes = normalize_routes_dataframe(routes_df)
    for origin, destination, time in routes.itertuples(index=False, name=None):
        if suppliers_df is not None and (origin not in graph or destination not in graph):
            raise ValueError("Route endpoints must exist in the supplier table")
        if not graph.has_edge(origin, destination) or time < graph[origin][destination]["time"]:
            graph.add_edge(origin, destination, time=float(time))
    return graph
