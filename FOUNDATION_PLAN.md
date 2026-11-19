# Backend foundation plan

Implement one stage at a time. The backend covers validated demo data, persistent local SQLite storage, directed routing, disruption scenarios, Monte Carlo comparison, risk metrics, saved results, and a CLI. Defer interface work until Stage 7 passes. Streamlit, frontend code, charts, web APIs, accounts, cloud services, Docker, and ML are outside this plan.

## Rules for every later stage

1. Start by reading applicable AGENTS.md instructions, this plan, root summary.md, and the actual current code and diff. Verify the previous stage's completion gate. Repair a narrow prerequisite when necessary and record the repair. Preserve working implementations and unrelated user changes.
2. Implement only the requested stage. Preserve `python main.py`, existing graph APIs and meaningful regression coverage. Keep computation independent of the CLI, storage, and future UI. Required behavior must be implemented and tested. Fake results, placeholder business logic, `pass`, and TODO implementations cannot satisfy a gate.
3. Use standard-library SQLite and unittest with existing NumPy, pandas, and NetworkX. Add dependencies only for a concrete need. Tests that use SQLite must use temporary databases and must never touch a user's development database.
4. After every stage or blocked attempt, update root `summary.md` and save a snapshot under `docs/progress/NN-stage-name.md`. Keep all prior snapshots. For a repeated attempt use a distinct descriptive suffix on its snapshot. Use the exact lowercase root filename `summary.md`.
5. In both records include the stage and verified status, branch/worktree and base revision, stage checklist, implemented behavior and changed files, migration/schema version, exact setup/run/test commands and actual results/counts, known issues and unverified checks, remaining work, next stage and its gate, and interface readiness. A failed required check keeps the stage incomplete. Record the genuine blocker and exact recovery step.
6. Return a short explanation, actual checks, and links to the summary and stage snapshot. Stop before the next stage. Use scoped local commits for verified work if repository policy permits. Exclude databases, exports, virtual environments, secrets, and unrelated changes. Do not merge main.

## Model contract

- Each comparison models one shipment between a selected pair of distinct nodes with alternative directed transit paths. Use integer node IDs compatible with Phase 1 and display names as metadata. Preserve `build_graph`, `shortest_path_metrics`, and their existing signatures and behavior, including the Phase 1 same-node query.
- Existing supplier `lead_time` represents days and route `time` represents hours. End-to-end hours equal `24 * source.lead_time + path transport hours`. Add source readiness once. Intermediate and destination supplier lead times do not contribute.
- Reliability is a node's per-trial probability of availability, including origin and destination. Background availability draws are independent across nodes, edge-time draws are independent across directed edges, and the two sets of draws are independent of one another. The chosen disruption adds an explicit shock to the stressed and mitigated conditions.
- Choose the fastest available path after trial conditions are known. This optimistic rerouting assumption represents full knowledge of conditions at route selection. The model has no inventory, capacity, or multi-product behavior and provides synthetic comparisons rather than calibrated real-world forecasts.
- Baseline, stressed, and mitigated runs share random samples and the same deadline. Mitigation retains the stress and adds a valid directed backup route. Its existence need not guarantee service in every trial.
- Use all trials as the denominator for rates. At or before the deadline is on time, delivered after it is late, and disconnected shipments are unserved with absent delivery time. Fragility is our defined deadline-risk score and equals `100 * (late + unserved) / trial_count`. Label time statistics as delivered-only and use absent values when all deliveries are unserved.
- Persist immutable, versioned network snapshots and run settings with saved results. Retain the exact snapshot, scenario and simulation settings, and algorithm version for audit and replay after newer data is added.

## Typed boundaries

The following are the field names and boundary signatures for later stages. Data records are frozen dataclasses with tuple collections. An optional value uses `Optional[T]`. Use Python 3.9-compatible typing for the supported fallback.

| Record | Fields |
| --- | --- |
| `Node` | `node_id: int, display_name: str, lead_time_days: float, reliability: float` |
| `Edge` | `origin_id: int, destination_id: int, transit_hours: float` |
| `NetworkRef` | `network_id: str, version: int` |
| `NetworkSnapshot` | `ref: NetworkRef, display_name: str, nodes: tuple[Node, ...], edges: tuple[Edge, ...]` |
| `Shipment` | `origin_id: int, destination_id: int, deadline_hours: float` |
| `NodeOutage` | `node_id: int` |
| `EdgeDelay` | `origin_id: int, destination_id: int, added_hours: float` |
| `RouteClosure` | `origin_id: int, destination_id: int` |
| `TransportSlowdown` | `origin_id: int, destination_id: int, factor: float` |
| `Scenario` | `disruption: Disruption, backup_edges: tuple[Edge, ...]`; `Disruption` is the union of the four disruption records. |
| `RunSettings` | `shipment: Shipment, scenario: Scenario, trials: int, seed: int, edge_jitter_fraction: float = 0, algorithm_version: str = "lognormal-pcg64-v1", sigma: float = 0`. The legacy jitter field is retained for stored settings compatibility. |
| `Delivery` | `path: Optional[tuple[int, ...]], transit_hours: Optional[float], end_to_end_hours: Optional[float]` |
| `ConditionTrials` | `baseline: tuple[Delivery, ...], stressed: tuple[Delivery, ...], mitigated: tuple[Delivery, ...]` |
| `RiskMetrics` | `trial_count: int, on_time_count: int, late_count: int, unserved_count: int, on_time_rate: float, late_rate: float, unserved_rate: float, fragility: float, delivered_mean_hours: Optional[float], delivered_p95_hours: Optional[float]`; `delivered_count` is derived from the delivered outcome counts. |
| `Criticality` | `node_id: int, fragility_increase_points: float` |
| `CriticalityReport` | `candidate_ids: tuple[int, ...], trial_count: int, baseline_fragility: float, ranking: tuple[Criticality, ...]` |
| `Comparison` | `baseline: RiskMetrics, stressed: RiskMetrics, mitigated: RiskMetrics, node_criticality: tuple[Criticality, ...]`; `stress_impact` and `mitigation_improvement` are derived percentage-point changes. |
| `SavedRun` | `run_id: str, network: NetworkRef, settings: RunSettings, result: Comparison, details: Optional[RunDetails]` |

Map Phase 1 columns `supplier_id`, `lead_time`, `origin`, `destination`, and `time` to the corresponding typed fields. Snapshot nodes are unique and sorted by ID, and edges are unique and sorted by ordered endpoint pair. Collapse duplicate Phase 1 routes to their minimum transit time at the adapter boundary. Reject invalid or missing references, boolean IDs/counts, nonfinite numeric values, negative times, reliability outside [0, 1], and empty IDs or display names. Require positive versions and trial counts, a nonnegative seed and deadline, Monte Carlo sigma in [0, 1], and strictly positive delay. Require one or more new directed backup edges between existing nodes, without self-loops or duplicate pairs. Stage 2 validates snapshot membership and new backup edges via `validate_scenario`. When both shipment endpoints survive deterministic stress, Stage 3 requires a simple shipment path using at least one backup edge. When an endpoint is out, report the stressed and mitigated shipment as unserved. Backup edges incident to unavailable nodes are omitted in both cases. Invalid domain input raises `ValueError`. Missing stored records raise `KeyError`. An unserved `Delivery` has all three fields absent.

## Module responsibilities

| Module | Boundary and ownership |
| --- | --- |
| `src/domain/` | Own the records and validation. Expose `src.domain.fixtures.demo_network() -> NetworkSnapshot` for a stable versioned fixture with a known shipment, disruption, and backup documented alongside it. |
| `src/storage/` | Use `SQLiteRepository(path: Path)` with `initialize() -> None`, `save_network(snapshot: NetworkSnapshot) -> NetworkRef`, `get_network(ref: NetworkRef) -> NetworkSnapshot`, `list_networks() -> tuple[NetworkRef, ...]`, `save_run(run: SavedRun) -> None`, and `get_run(run_id: str) -> SavedRun`. Own migrations, transactions, foreign keys and serialization. Enable SQLite foreign keys per connection. Identical fixture reseeding is idempotent. Reject different data under an existing snapshot key. Save each run atomically with a foreign key to its immutable snapshot. |
| `src/graph/` | Reuse the existing graph builder and Dijkstra implementation. Adapt snapshots and expose `deterministic(network: NetworkSnapshot, shipment: Shipment, scenario: Scenario) -> ConditionTrials` with one delivery per condition. Apply outage by removing the node and incident edges, closure by removing the selected directed edge, slowdown by multiplying its transport hours by a finite factor of at least 1, and legacy delay by adding hours. Route baseline, stress and mitigation from independent graph copies. Use canonical node and edge order to make tie handling repeatable. |
| `src/simulation/` | `simulate(network: NetworkSnapshot, settings: RunSettings) -> SimulationResult` returns aligned baseline, stressed and mitigated delivery tuples with statuses and replay metadata. Use shared node availability and mean-preserving lognormal transport samples, then apply stress and backup rules through the deterministic scenario layer. |
| `src/scoring/` | `score(deliveries, deadline_hours) -> RiskMetrics` and `score_comparison(trials, deadline_hours) -> Comparison` score actual trial records. `rank_node_criticality(network, settings, candidate_ids=None) -> CriticalityReport` reports paired outage sensitivity, evaluated candidate IDs, and trial budget. |
| `src/pipeline.py` | Compose computation and persistence through `compare(network: NetworkSnapshot, settings: RunSettings) -> Comparison`, `compare_and_save(repository: SQLiteRepository, ref: NetworkRef, settings: RunSettings) -> SavedRun`, and `replay_run(repository: SQLiteRepository, run_id: str) -> ReplayResult`. `compare_preset(repository, ref, preset_id, ...)` resolves stored defaults and accepts shipment and sigma overrides. Replay returns a typed `ReplayResult` with warnings, validates the saved snapshot fingerprint and environment, and checks exact trial, metric, and sensitivity equality. |
| `src/cli.py` | Own arguments, user-facing output, exit status and repository lifecycle. The legacy `main.py` continues to run Phase 1. |
| `src/utils/export.py` | `export_run(run: SavedRun, destination: Path, *, overwrite: bool = False)` writes `summary.csv`, `trials.csv`, and strict `metadata.json` from persisted results. |

## Storage and fixture contracts

- `ScenarioPreset(preset_id: str, network: NetworkRef, shipment: Shipment, scenario: Scenario)` names a scenario on a specific network version. Use `save_preset(preset: ScenarioPreset) -> None` and `get_preset(ref: NetworkRef, preset_id: str) -> ScenarioPreset`. Use `seed(fixtures: tuple[tuple[NetworkSnapshot, ScenarioPreset], ...]) -> None` with `src.domain.fixtures.bundled_fixtures()` to seed both bundles atomically.
- Schema 2 retains the tables from schema 1 and adds a checked disruption kind and slowdown factor to scenario presets. It migrates existing outage and absolute-delay presets and preserves their backup routes. It uses `networks`, `nodes`, `routes`, `scenario_presets`, `scenario_backup_routes`, `runs`, and `run_results`. Network versions are identified by `(network_id, version)`. Node and route references for networks and presets are scoped by both columns. Run settings and results are stored as typed JSON payloads, validated by the repository, with a foreign key from each run to its network version and from its result to the run.
- The demo JSON under `data/fixtures/` uses route triples in origin, destination, hours order. The coastal port outage preset has a 50-hour deadline. With background conditions disabled, the port route takes 42 hours including source readiness, the inland route takes 63 hours, and the separate backup via the ferry terminal takes 45 hours. The tiny fixture gives 29, 36, and 32 hours with a 32-hour deadline.

## Stage 3 deterministic routing

- Use `src.graph.scenarios.build_snapshot_graph(network)` to adapt a loaded `NetworkSnapshot` through the Phase 1 builder. Use `deterministic(network, shipment, scenario)` to validate the selection and return one delivery per condition. Call `Delivery.status(shipment.deadline_hours)` for `on_time`, `late`, or `unserved`.
- Mitigation starts with the stressed graph. An existing directed route, including a closed route, cannot be supplied as a backup. The selected disruption applies to one node or one directed route.

## Stage 4 Monte Carlo

- Validate at most 25 nodes, 60 distinct directed routes including backups, 10,000 trials, and a finite sigma in [0, 1] before allocating samples. New runs use `sigma` and require the legacy jitter field to be zero. Reject unsupported algorithm versions.
- Model `lognormal-pcg64-v1` takes four uint32 words from `default_rng(seed)` and derives separate streams with a node or edge namespace and two uint32 words per signed ID. Draw one uniform per node per trial and one standard normal per directed route per trial. Use `uniform < reliability` for availability and `base_hours * exp(sigma*z - sigma*sigma/2)` for route hours. Apply disruptions after sampling. A disruption whose target is already unavailable has no additional effect.
- Reuse the streams across conditions and sample the union of their edges, including backups. A slowdown factor of 1 is a no-op for the stressed condition. Only the mitigated condition adds backup routes, and their endpoints must still be available.
- `SimulationResult` extends `ConditionTrials` with `metadata`, which records the network version, exact run settings including the model version, and the Python, NumPy, pandas and NetworkX versions. Its `statuses` exposes the three aligned status sequences using the recorded deadline. Save these replay inputs with comparisons in Stage 6.

## Stage 5 risk scoring and sensitivity

- Counts and rates are mutually exclusive for on-time, late and unserved outcomes. Each rate divides by all trials. Delivered count is on-time plus late. Compute mean and linearly interpolated P95 from delivered end-to-end hours. Both times are absent when nothing is delivered.
- Stress impact is `100 * (stressed_on_time_rate - baseline_on_time_rate)`. Mitigation improvement is `100 * (mitigated_on_time_rate - stressed_on_time_rate)`. Both are percentage-point changes. Use `FRAGILITY_LABEL` when displaying the defined deadline-risk score.
- Sensitivity evaluates up to eight candidates. By default choose the first eight transit IDs in ascending order. Accept an explicit tuple of up to eight unique transit IDs. Exclude origin and destination. Evaluate the first `min(run_trials, 500)` shared draws, once for the matching baseline and once per individual outage, without the intervention or backup from the main comparison. Rank by descending fragility increase, then ascending node ID. Stage 6 must disclose the exact evaluated IDs, trial budget and matching baseline fragility alongside the ranking.

## Stage 6 persistence and CLI

Schema 3 adds preset sigma and complete run details. Each full run includes a
canonical snapshot and SHA-256 fingerprint, environment and code provenance,
three trial sets, the sensitivity report, and separate computation timings.
The repository saves these details, settings, and metrics in one transaction.
Summary-only records remain readable after migration.

Invoke as `python -m src.cli [--db PATH] COMMAND`. The global `--db` option precedes the subcommand. Its default is `var/supply_chain.sqlite3` relative to the working directory.

| Command | Purpose |
| --- | --- |
| `init-db` | Create or migrate the local database. |
| `seed-demo` | Save the validated, versioned demo fixture idempotently. |
| `list-networks` | List saved network IDs and versions. |
| `compare` | Use `--network demo-v1 --preset port-outage --seed 42 --trials 2000` with optional `--origin`, `--destination`, `--deadline-hours`, and `--sigma` overrides. Save the comparison and print its run ID. |
| `show-run --run-id ID` | Read saved settings and metrics. |
| `replay-run --run-id ID` | Recompute with the stored snapshot, settings and supported algorithm version. |
| `export-run --run-id ID --output-dir DIR [--overwrite]` | Export saved results to a user-selected file. |

## Stages and completion gates

| Stage | Scope | Required gate |
| --- | --- | --- |
| 1. Baseline and contracts | Audit current refs and checkout, isolate the backend branch, verify environment and Phase 1 behavior, and publish the plan, summary, and baseline snapshot. | Original CLI succeeds, existing unittest suite passes, pip check is clean, and all three records are present with verified outcomes. |
| 2. Domain, storage, and fixtures | Implement domain validation, deterministic versioned demo data, SQLite migration and network repository. | Fresh and repeated initialization succeed, demo reseeds safely, immutable versions round-trip after reconnect, invalid data is rejected atomically and Phase 1 regressions pass. |
| 3. Deterministic scenarios | Apply node outages, directed closures, slowdown, absolute delay, and backup routes to directed routing. | Tests show exact path and hour calculations, single source readiness, rerouting, no-path semantics, stress retained with backup, and unchanged input snapshots. |
| 4. Monte Carlo | Implement shared seeded draws, lognormal transport volatility, per-trial routing, and trial outcomes. | Tests prove reproducibility, aligned draws, boundary availability behavior, deterministic agreement with variation disabled, and explicit unserved deliveries. |
| 5. Metrics and criticality | Compute outcome rates, fragility, delivered-only time statistics and transit-node ranking. | Hand-checkable tests cover mixed, all-delivered and all-unserved cases, deadline equality, percentile convention, and tied rankings. |
| 6. Service, CLI, persistence, and exports | Compose comparison and replay, persist runs, add CLI commands and exports. | A CLI subprocess workflow against a temporary SQLite file exercises every command, reopens saved runs, replays after a newer snapshot exists and verifies the three-file CSV and JSON export bundle. |
| 7. Final integration and handoff | Verify fresh setup and public workflows. Document setup, examples, storage, assumptions and limitations. | Full suite and pip check pass, Phase 1 and new end-to-end CLI workflows succeed from a fresh environment, and migration, replay, exports, and interface readiness are documented. |

Every gate after Stage 1 also requires the full existing regression suite and the stage records.
