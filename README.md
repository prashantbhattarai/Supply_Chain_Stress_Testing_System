# Supply Chain Stress Testing System

Phase 1 builds synthetic supplier and transportation data, models a directed network,
and finds the fastest route using Dijkstra. No Monte Carlo or machine learning is
implemented by this phase.

## Setup and run

From the repository root, use Python 3.9 or later:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
python -m unittest discover -s tests -v
```

If the workspace virtual environment already exists, activate it rather than recreating it.
The Phase 1 runner prints results and does not write data files.

The default seeded example produces 20 suppliers, 80 route rows, and a directed
graph with 20 nodes and 72 edges. Its fastest path is `1 -> 20`, taking 14 hours.
Duplicate route pairs explain why edge count is smaller than route count.

## Data and graph rules

- Suppliers: unique integer `supplier_id`, `lead_time` in days (5–39), and
  `reliability` between 0.80 and 0.99.
- Routes: unique `route_id`, integer `origin` and `destination`, and `time` in
  hours (2–14). Endpoints use the inclusive requested range. Self-routes are
  avoided; a nonempty table starts with a guaranteed `start -> end` route.
- Each generator uses its own optional random seed. Passing the same seed repeats
  its output without changing NumPy's global random state.
- `build_graph(routes, suppliers)` adds all supplier nodes, including isolated
  suppliers, with their attributes. Unknown endpoints raise `ValueError`.
  `build_graph(routes)` also supports route-only graphs.
- Edges point from origin to destination. Reverse travel requires a separate route.
  Repeated ordered pairs keep the minimum time, independent of input order.
- Route normalization accepts aliases such as `from,to,duration`, drops missing
  endpoints and invalid, negative, or non-finite times, and raises `ValueError`
  for nonempty tables missing required columns. Zero time is accepted for uploaded data.
- Dijkstra returns both the node sequence and total transit hours. It handles
  empty graphs, missing endpoints, same-node queries, and unreachable destinations
  with explicit statuses. Supplier lead time is a separate attribute and is not
  added to edge transit time.

## Files

| File | Purpose |
| --- | --- |
| `main.py` | Run the full Phase 1 example |
| `src/data_generation/suppliers.py` | Synthetic supplier data |
| `src/data_generation/routes.py` | Synthetic directed routes |
| `src/data_generation/routes_io.py` | Normalize route tables and read CSV uploads |
| `src/data_generation/merge_data.py` | Join suppliers with outgoing routes |
| `src/cleaning/cleaning.py` | Shared supplier cleaning and validation |
| `src/graph/build_graph.py` | Canonical NetworkX DiGraph builder |
| `src/graph/graph_analysis.py` | Shared Dijkstra analysis and result object |
| `src/utils/file_loader.py` | CSV and JSON file readers |
| `tests/test_phase1.py` | Automated unittest coverage |
| `PHASE1_EXPLANATION.md` | Function explanations and design decisions |

Docker, dashboards, deployment configuration, and failure simulation are outside
the Phase 1 foundation and are not required to run its application or tests.
The misspelled `builld_graph.py` and old cleaning module remain compatibility imports,
so there is one implementation of each shared function.

Tests cover reproducibility, data constraints, empty inputs, directed edges,
duplicate routes, isolated suppliers, weighted shortest paths, unreachable nodes,
invalid weights, CSV normalization, file loading, compatibility imports, and the
complete pipeline (including execution from another working directory).
