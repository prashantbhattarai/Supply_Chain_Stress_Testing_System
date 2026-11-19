# Backend demo and handoff

## Local setup

From the repository root, use Python 3.9.6, the release-verified interpreter.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
python -m unittest discover -s tests -v
python main.py
python -m src.cli --help
```

The final checks ran on macOS 26.6.2, arm64, with SQLite 3.51.0, NumPy 2.0.2,
pandas 2.3.3, and NetworkX 3.2.1. Python 3.12 and other platforms were not verified.

## Terminal demonstration

This example creates a temporary database, uses the printed run ID, and
opens the run in new processes to inspect, replay, and export it.

```sh
demo_dir=$(mktemp -d)
db="$demo_dir/demo.sqlite3"
python -m src.cli --db "$db" init-db
python -m src.cli --db "$db" seed-demo
python -m src.cli --db "$db" list-networks
python -m src.cli --db "$db" compare --network demo-v1 --preset port-outage --seed 42 --trials 2000 | tee "$demo_dir/compare.txt"
run_id=$(sed -n 's/^Run ID: //p' "$demo_dir/compare.txt")
test -n "$run_id"
python -m src.cli --db "$db" show-run --run-id "$run_id"
python -m src.cli --db "$db" replay-run --run-id "$run_id"
python -m src.cli --db "$db" export-run --run-id "$run_id" --output-dir "$demo_dir/export"
```

`demo-v1` aliases `coastal-demo-v1`, a synthetic network with 11 nodes. The
shipment goes from Cedar Components (1) to Metro Customer (10). Harbor Port
(4) is the primary-path bottleneck. The outage leaves a slower inland path.
Mitigation retains that outage and adds the ferry route from node 8 to node 9.
Without background failures or transit volatility, these choices yield 42, 63,
and 45 end-to-end hours against the 50-hour deadline. The `tiny-v1` fixture has
four nodes and deterministic totals of 29, 36, and 32 hours.

The demo uses sigma 0.15. Override a preset with `--origin`, `--destination`,
`--deadline-hours`, or `--sigma`. Endpoints must exist in the stored network
and the backup must remain valid for the resulting shipment.

The release run printed ID `604a2568-56a8-4e5f-bbd0-399fd70e0139`.
The following are excerpts from that run:

```text
coastal-demo-v1 (alias: demo-v1)
tiny-v1
Stress impact: -87.35 percentage points
Mitigation improvement: +91.20 percentage points
Comparison runtime: 0.390780 s
Criticality runtime: 0.285374 s
Replay verified: 604a2568-56a8-4e5f-bbd0-399fd70e0139
```

Baseline, stressed, and mitigated on-time rates were 87.35%, 0%, and 91.20%.
The export contained three summary rows and 6,000 trial rows.

## Storage, replay, and exports

The CLI defaults to `var/supply_chain.sqlite3`. `init-db` creates or migrates it
transactionally. Schema 1 created network and run tables. Schema 2 expanded
the scenario types. Schema 3 added preset volatility and complete run details.
Back up an existing database before migrating it. `seed-demo` is repeatable.
Use a new network version for topology or node-setting changes. Each complete
run retains its own snapshot, SHA-256 fingerprint, inputs, environment,
deliveries, unique run ID, and measured sensitivity. Treat SQLite
as application-managed data. Direct SQL edits can bypass repository rules.

Replay uses the embedded snapshot and checks model, Python, NumPy, pandas,
and NetworkX versions. It checks exact equality of recomputed deliveries,
metrics, and sensitivity. A dirty or unavailable revision is reported.
Pinned versions are necessary for this replay contract. Platform-level
numerical behavior and uncommitted code can still affect reproducibility.
Older summary-only records can be inspected but lack inputs for full replay.

Exports contain `summary.csv`, `trials.csv`, and `metadata.json` from the
persisted run. CSV uses blank path and times for unserved deliveries.
JSON summary time statistics are null when no shipments were delivered.
Output files require explicit `--overwrite` for replacement.

## Model and limitations

Directed shortest paths use sampled transport hours. End-to-end delivery time
adds 24 hours per source lead-time day once. Node availability and route
time fluctuations are independent. Conditions share entity-keyed random
samples. Rerouting optimistically knows the realized state before selecting a
route. Background disruptions are synthetic, and the model does not estimate
capacity, inventory, correlated failures, or calibrated real-world risk.

The on-time deadline is inclusive. Rates divide by all trials, unserved is
distinct from late, and delivered-only hours exclude unserved trials. Fragility
is the defined deadline-risk score, 100 times the late-or-unserved rate.
Sensitivity evaluates at most eight transit nodes and 500 matching baseline
trials. Simulation is capped at 25 nodes, 60 routes including backups, 10,000
trials, and sigma 1. Dense backup-path validation has not been benchmarked.

## Stable backend entry points

| Function or record | Interface contract |
| --- | --- |
| `SQLiteRepository(path)` | Call `initialize()` once per database lifecycle or upgrade. Use `list_networks()`, `get_network(ref)`, `get_preset(ref, preset_id)`, and `get_run(run_id)` for reads. |
| `compare_preset(repository, ref, preset_id, ...)` | Resolve the saved preset, apply optional shipment and volatility overrides, and return the persisted `SavedRun`. |
| `compare_and_save(repository, ref, settings)` | Persist a comparison for explicit validated `RunSettings` on a stored version. |
| `compare(network, settings)` | Compute a typed `Comparison` without writing a run. |
| `replay_run(repository, run_id)` | Return a verified `ReplayResult` containing the saved run and provenance warnings. |
| `export_run(run, destination, overwrite=False)` | Write a complete saved run's export bundle. |
| `SavedRun`, `RunDetails`, `Comparison` | Read the saved metrics, snapshot, per-condition `Delivery` records, provenance, and `CriticalityReport`. For legacy runs, `details` is absent. |

The service returns records without printing. Handle `ValueError` for
invalid inputs or incompatible replay, `KeyError` for missing records, and
SQLite or filesystem errors for persistence and export failures.
