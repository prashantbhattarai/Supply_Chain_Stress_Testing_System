# Phase 1 function guide

## How the pieces fit together

`main.py` generates suppliers and routes with a fixed seed, merges the tables for
inspection, builds a directed graph, and asks Dijkstra for the fastest path.
Supplier IDs and graph node IDs refer to the same entities. A route is an ordered
pair: `1 -> 2` does not imply `2 -> 1`. Transport hours are edge weights; supplier
lead times use days and are not combined with those hours.

## Data generation

`generate_suppliers(n=50, seed=None)` in `suppliers.py` validates a non-negative
integer count, creates IDs 1 through n, and generates lead times and reliability.
It calls `clean_suppliers` before returning a pandas DataFrame. Zero returns an
empty table with the expected columns. Each call has a local NumPy generator:
a supplied seed repeats output, while `None` permits fresh samples.

`generate_routes(n=100, start=1, end=20, seed=None)` validates the count and integer
bounds (`start < end`). Both bounds are included. An origin is chosen at random;
a nonzero modular offset picks a different destination without retry loops.
For a nonempty table the first route connects start directly to end, ensuring the
default demonstration has a path. This does not guarantee that every pair is
reachable. Route IDs are unique, although endpoint pairs may repeat. Transit
hours are integers 2 through 14. Zero routes returns an empty four-column table.

`merge_supplier_routes(suppliers, routes)` in `merge_data.py` performs a left join
on `supplier_id = origin`. Every supplier survives, including those without an
outgoing route (their route fields are missing). Suppliers with several outgoing
routes appear several times. `validate="one_to_many"` prevents duplicate supplier
IDs from silently multiplying rows. Importing this module does not generate data
or print output; its demonstration runs only under the main guard.

## Cleaning and input

`clean_suppliers(df)` copies its input, normalizes column names, checks required
columns and unique nonmissing IDs, and converts lead time and reliability to
floats. Values must be finite; lead time cannot be negative and reliability must
be between zero and one. It raises errors rather than silently inventing supplier
values. The caller's table stays unchanged. `src/cleaning/simulation.py` re-exports
this function instead of maintaining a duplicate implementation.

`_standardize_column_key(name)` in `routes_io.py` trims and lowercases headers,
replacing spaces and hyphens with underscores. `normalize_routes_dataframe(df)`
uses it to recognize aliases and returns just `origin`, `destination`, and `time`.
It converts time strings to numbers, drops malformed rows, negative times, and
infinities, and resets the index. Missing endpoints are dropped too. Empty or
None input becomes an empty canonical table. Missing columns in nonempty input
raise `ValueError`. Endpoint values are preserved; uploaded IDs must therefore
use consistent types. Normalization does not create reverse routes.

`read_routes_csv_bytes(data)` reads uploaded bytes with an in-memory buffer and
normalizes them. `read_routes_csv_stream(buffer)` does the same for an open binary
stream. Neither requires a project-relative filename.

`load_csv(path)` in `file_loader.py` reads a UTF-8 CSV into a list of dictionaries;
values stay strings. `load_json(path)` parses a UTF-8 JSON file into Python values.
Both use `with` to close files even on errors.

## Graph construction

`build_graph(routes_df, suppliers_df=None)` in `build_graph.py` creates a NetworkX
`DiGraph`. Optional supplier data is cleaned and added as nodes first, retaining
lead time, reliability, and nodes with no routes. When suppliers are supplied,
a route referring to an unknown supplier raises `ValueError`. Without suppliers,
route endpoints create nodes.

The builder normalizes routes and adds `time` as a float edge attribute. If an
ordered pair repeats, only its fastest time is retained. Thus input row order
does not decide the route cost. The graph intentionally summarizes transport
options rather than preserving multiple parallel edges. Iterating with
`itertuples` avoids pandas row conversion turning integer node IDs into floats.
The misspelled `builld_graph.py` re-exports this canonical builder for compatibility.

## Dijkstra analysis

`PathMetrics` in `graph_analysis.py` is an immutable result object with `path`
(a tuple or None), `total_time` (hours or None), `status`, and optional `detail`.
Its `is_connected` property is true whenever a path exists, including a same-node
path with zero travel time.

`shortest_path_metrics(graph, source, target, weight="time")` validates a directed
simple graph and finite non-negative edge weights. This avoids NetworkX silently
assuming a missing weight is one. It calls `nx.single_source_dijkstra` once to
get both total weight and path. Dijkstra minimizes total weight, which can prefer
several short legs over one slow direct edge. Invalid graph/weight input raises
`ValueError`; ordinary unavailable-path cases return statuses:

| Status | Meaning |
| --- | --- |
| `ok` | A directed path exists |
| `empty_graph` | No nodes exist |
| `missing_source` | Source ID is absent |
| `missing_target` | Target ID is absent |
| `same_node` | Existing source equals target; path has one node and time zero |
| `no_path` | Both endpoints exist but target cannot be reached |

Validation happens before endpoint lookup; empty graph takes priority over missing
endpoints, and missing source takes priority over missing target. `_demo()` prints
a seeded example with `python -m src.graph.graph_analysis`.

Failure simulation, Monte Carlo algorithms, and machine learning are outside
the Phase 1 foundation.

## Entry points and retained exercises

`run_phase1(seed=42)` in root `main.py` returns suppliers, routes, merged data,
graph, and path result. It uses 20 suppliers and the same 1..20 endpoint range
for 80 routes, so generated route endpoints match supplier IDs.

`main()` prints counts, Dijkstra status, route sequence, and total hours. It does
not write files. Its main guard keeps imports quiet. `src/utils/main.py` forwards
to it for `python -m src.utils.main`; the recommended command is `python main.py`.

`build_sample_graph()` in `graph_basics.py` remains a small named-node teaching
example using the same directed graph and `time` convention. Teaching exercises
are separate from the Phase 1 pipeline.

Docker, dashboards, deployment configuration, and deterministic stress helpers
are not included in the Phase 1 foundation.

## Automated checks

`GenerationTests` checks counts, IDs, ranges, fixed seeds, independence from global
random state, invalid arguments, empty generation, and cleaning validation.
`GraphTests` checks directed edges, fastest duplicate selection, supplier attributes,
isolates, weighted paths, all path statuses, invalid weights, input normalization,
and unknown supplier endpoints. `IntegrationTests` checks the full pipeline,
left-join behavior, file readers, old import compatibility, quiet imports, and
running the root entry point from another directory. `setUp()` supplies a small
known graph where 1 -> 2 -> 3 costs 5 hours while direct 1 -> 3 costs 12.

Run `python -m unittest discover -s tests -v` from the repository root. Tests use
Python's standard unittest framework and temporary directories, without requiring
an external service. The seeded main example prints 20 nodes, 72 edges, path
`1 -> 20`, and 14 total transit hours.
