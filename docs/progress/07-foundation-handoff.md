# Stage 07 foundation handoff snapshot

**BACKEND_READY_FOR_UI**

Stage 7 completed the backend release gate. Interface implementation has not started.

## Stage status

| Stage | Verified status |
| --- | --- |
| 1. Baseline and contracts | Complete. Phase 1 CLI and 17 original tests verified. |
| 2. Domain, storage, and fixtures | Complete. Validated fixtures, immutable network versions through the repository, and transactional SQLite verified. |
| 3. Deterministic scenarios | Complete. Directed disruption routing, backup behavior, and day/hour conversion verified. |
| 4. Monte Carlo | Complete. Aligned seeded draws, unserved outcomes, and workload limits verified. |
| 5. Risk and criticality | Complete. All-trial rate denominators, delivered-only times, percentage-point deltas, and paired sensitivity verified. |
| 6. Backend workflow | Complete. Service, SQLite persistence, replay and CLI exports verified. |
| 7. Foundation handoff | Complete. Fresh-environment checks, full temporary database workflow, artifact audit, and integration documentation verified. |

## Branch, audit, and changes

- Worktree `/private/tmp/supply-chain-foundation-backend`, branch `foundation-backend`, started clean at Stage 6 commit `fa7d14b2798de8f82e871e6703133905e3a2d3f1`. GitHub returned the same SHA. No applicable AGENTS.md was found. The existing environment passed all 64 Stage 6 tests, pip check, the original CLI, and CLI help.
- [x] Audited validation, units, constraints, migrations, reseeding, rollback, versioned snapshots, directed routing and scenario copies, paired samples, workload limits, outcome denominators, scoring, criticality, persistence, replay, exports, and CLI errors against the implementation and tests.
- [x] Fixed an integrity gap in `src/storage/__init__.py`. Direct callers can no longer save a full run whose summary disagrees with its trial records. `src/pipeline.py` now checks the Git root before recording code provenance, so an archive nested in another repository cannot inherit its revision.
- [x] Added two targeted regressions to `tests/test_backend_workflow.py` for inconsistent run rejection and fixture loading from another directory. Reused existing migration, rollback, routing, replay and export tests.
- [x] Audited tracked files and credential markers. No databases, sidecars, virtual environments, generated exports, or recognized credential files or key markers were found. The Phase 1 commit remains one ancestor in the branch, and the original Phase 1 CLI, graph builder, shortest-path implementation, and test file match `f780cee`.
- [x] Completed `README.md`, `FOUNDATION_PLAN.md`, `BACKEND_DEMO.md`, `summary.md`, and `docs/progress/07-foundation-handoff.md`.
- SQLite schema remains version 3. Stage 7 adds no migration. The demo returned `integrity_check = ok` and an empty `foreign_key_check`.

## Fresh environment checks

Used a clean source copy at `/private/tmp/supply-stage7.XowkJH/source`, created with `git archive HEAD | tar -x` plus the three scoped Stage 7 Python files. There was no Git metadata or existing runtime data in the source copy.

Ran `python3 -m venv .venv` and `source .venv/bin/activate`. A sandboxed package-index attempt failed. With network approval, `python -m pip install --disable-pip-version-check -r requirements.txt` installed all 17 pins. The platform was macOS 26.6.2 (Darwin 25.6.0), arm64, with Python 3.9.6, SQLite 3.51.0, NumPy 2.0.2, pandas 2.3.3, and NetworkX 3.2.1.

| Command | Actual result |
| --- | --- |
| `python -m pip check` | Exit 0. No broken requirements found. |
| `python -m unittest discover -s tests -v` | Exit 0. All 66 tests passed in 22.255 s. |
| `python main.py` | Exit 0. 20 suppliers, 80 routes, 20 nodes and 72 edges. Shortest route `1 -> 20` took 14 transit hours. |
| `python -m src.cli --help` | Exit 0. Help listed all seven commands and the default database. |
| `git diff --check` | Exit 0. No whitespace errors. |

## Verified temporary database demo

```sh
db=/private/tmp/supply-demo7.83NJ6j/demo.sqlite3
python -m src.cli --db "$db" init-db
python -m src.cli --db "$db" seed-demo
python -m src.cli --db "$db" seed-demo
python -m src.cli --db "$db" list-networks
python -m src.cli --db "$db" compare --network demo-v1 --preset port-outage --seed 42 --trials 2000
python -m src.cli --db "$db" show-run --run-id 604a2568-56a8-4e5f-bbd0-399fd70e0139
python -m src.cli --db "$db" replay-run --run-id 604a2568-56a8-4e5f-bbd0-399fd70e0139
python -m src.cli --db "$db" export-run --run-id 604a2568-56a8-4e5f-bbd0-399fd70e0139 --output-dir /private/tmp/supply-demo7.83NJ6j/export
```

Every command exited 0. The list contained `coastal-demo-v1` (alias `demo-v1`) and `tiny-v1`. The separately opened run matched the compare output exactly. Replay verified the 2,000 trials per condition. Exports contained three summary rows and 6,000 trial rows. From the temporary database directory, importing `bundled_fixtures()` with the clean source on `PYTHONPATH` loaded the 11-node and four-node fixtures by their preset IDs.

| Condition | On time | Late | Unserved | Fragility | Mean delivered | P95 delivered |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | 1747 (87.35%) | 144 | 109 | 12.65 | 43.621 h | 61.885 h |
| Stressed | 0 (0%) | 1797 | 203 | 100.00 | 62.959 h | 68.182 h |
| Mitigated | 1824 (91.20%) | 74 | 102 | 8.80 | 45.505 h | 49.319 h |

Comparison took 0.390780 s and criticality took 0.285374 s. Criticality used nodes 2–9 and 500 matched trials with baseline fragility 14.80. The archive had no Git metadata, so replay reported unavailable code provenance and still verified exact results.

## Limitations and handoff

Python 3.12, other platforms, and cross-version reproducibility remain unverified. Verify another interpreter with a separate virtual environment, pinned installation, the four release commands, and the temporary database workflow. Dense backup validation has not been benchmarked. The model is synthetic, uses independent background draws and optimistic rerouting, and tracks one shipment. Legacy summary-only runs lack trial data for replay and full export.

No foundation stages remain. A future interface can use the stable Python entry points and typed records documented in `BACKEND_DEMO.md`. Interface implementation needs its own scope.
