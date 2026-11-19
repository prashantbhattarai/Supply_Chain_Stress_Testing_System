# Supply Chain Stress Testing System

The local backend compares baseline, stressed, and mitigated shipments on a directed
supply network. It saves reproducible Monte Carlo inputs, delivery trials, risk
metrics, and measured transit-node sensitivity in SQLite. The original Phase 1
example remains available through `python main.py`.

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

## Persistent backend workflow

From the repo root with the virtual environment active:

```bash
python -m src.cli --help
python -m src.cli init-db
python -m src.cli seed-demo
python -m src.cli list-networks
run_output=$(python -m src.cli compare --network demo-v1 --preset port-outage --seed 42 --trials 2000)
printf '%s\n' "$run_output"
run_id=$(printf '%s\n' "$run_output" | sed -n 's/^Run ID: //p')
python -m src.cli show-run --run-id "$run_id"
python -m src.cli replay-run --run-id "$run_id"
python -m src.cli export-run --run-id "$run_id" --output-dir "exports/$run_id"
```

The default database is `var/supply_chain.sqlite3`. Use the global `--db PATH`
before the subcommand to select another database. `init-db` creates or migrates
the database, and `seed-demo` is safe to repeat. `demo-v1` aliases the stored
`coastal-demo-v1` snapshot.

The coastal `port-outage` preset uses origin 1, destination 10, a 50-hour deadline,
and lognormal volatility sigma 0.15. Override these with `--origin`,
`--destination`, `--deadline-hours`, or `--sigma` on `compare`. Simulation
supports up to 25 nodes, 60 directed routes including backups, 10,000 trials,
and sigma in [0, 1]. Node failures and route times are independent background
draws. Routing has full knowledge of the sampled conditions. Simulation adds
source readiness in hours once. Its fragility metric is the percentage of all
trials that are late or unserved.

Replay uses the run's embedded snapshot, seed, settings, and model version.
It rejects incompatible Python, NumPy, pandas, NetworkX, or model versions
and verifies the recomputed trials, scores, and sensitivity against saved
results. A different revision or dirty or unknown worktree is reported because
a Git commit and dirty flag cannot reconstruct uncommitted source code. Older
summary-only records can be shown, while replay and trial export require a
complete run.

Exports contain `summary.csv`, `trials.csv`, and `metadata.json`. The bundle
includes outcomes and counts, hours, run inputs, environment and snapshot
details, and the sensitivity candidate and trial budget. Unserved trials have
blank path and hour fields in CSV. Missing summary times are JSON null.
Specify `--overwrite` to replace an existing export bundle.

## Phase 1 data and graph rules

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
| `src/cli.py` | Initialize, seed, compare, inspect, replay, and export |
| `src/pipeline.py` | Run and verify persisted comparisons |
| `src/storage/` | SQLite repository and migrations |
| `src/utils/export.py` | Export persisted comparison bundles |
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
