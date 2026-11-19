# Stage 03 deterministic scenarios snapshot

**Stage 3 of 7, deterministic scenarios, completed and verified.** Stage 4 has not started. The backend is not ready for interface work.

## Branch and prerequisite

- Worktree `/private/tmp/supply-chain-foundation-backend`, branch `foundation-backend`, Stage 3 base `9d6d7a251ebac47c6792bc45447f0566569cb13e`. The worktree started clean. No applicable AGENTS.md was found.
- `git rev-parse HEAD` and `git ls-remote origin refs/heads/foundation-backend` matched at the Stage 2 base. The Stage 2 gate passed again, with all 30 tests, the original CLI, and pip check succeeding.

## Stage checklist and changes

- [x] Connect versioned SQLite snapshots to the canonical directed Phase 1 graph builder and Dijkstra search. `src/graph/scenarios.py` adapts node and route records and preserves isolated nodes and the existing Phase 1 graph APIs and duplicate-edge minimum behavior.
- [x] Validate shipment selection and implement node outage, directed route closure, slowdown, and legacy absolute delay. `src/domain/__init__.py` adds `RouteClosure`, `TransportSlowdown`, and `Delivery.status`. Slowdown requires a finite factor of at least 1, and a transformed edge time must remain finite.
- [x] Evaluate baseline, stress and mitigation on separate graphs. `src/graph/scenarios.py` omits backup edges incident to outaged nodes, rejects original route pairs as backups even when closed, and requires a simple shipment path using a backup edge when both shipment endpoints survive. An origin or destination outage yields an unserved stressed and mitigated shipment. A disconnected condition has absent path and times.
- [x] Report transport hours and end-to-end hours separately. End-to-end adds 24 times the origin's lead time in days once. A delivery at the deadline is on time. The tiny fixture yields baseline 5 transit/29 total hours, stressed 12/36, and mitigated 8/32 against a 32-hour deadline.
- [x] Preserve saved presets and support the expanded disruption contract. `src/storage/002_disruptions.sql` upgrades SQLite `user_version` from 1 to 2 transactionally. It rebuilds the preset and preset-backup tables with a checked disruption kind, scoped references and factor constraints, and copies prior rows. `src/storage/__init__.py` handles new presets and saved-run settings while retaining the prior JSON payload format.
- [x] Verify the gate. `tests/test_scenarios.py` adds nine scenario tests and `tests/test_storage.py` adds one migration test and verifies schema version 2. `FOUNDATION_PLAN.md`, `summary.md`, and `docs/progress/03-scenarios.md` record the updated contracts and outcomes.

## Setup and checks

Ran from the existing worktree with `source .venv/bin/activate`. The command `python -c 'import sqlite3, sys; print(sys.version.split()[0], sqlite3.sqlite_version)'` reported Python 3.9.6 and SQLite 3.51.0. No new dependencies were needed. Databases used by the tests were temporary. Open an existing database with `SQLiteRepository(path).initialize()` to apply the migration before reading or writing through the repository.

| Command | Verified result |
| --- | --- |
| `python -m unittest tests.test_scenarios tests.test_storage -v` | Exit 0, 23 tests passed. |
| `python -m unittest discover -s tests -v` | Exit 0, 40 tests passed, including all 17 original Phase 1 tests. |
| `python main.py` | Exit 0, 20 suppliers, 80 route rows, 20 graph nodes and 72 edges. Shortest route `1 -> 20` took 14 transit hours. |
| `python -m pip check` | Exit 0, no broken requirements. The sandbox disabled the pip cache. |
| `git diff --check` | Exit 0, no whitespace errors. |

## Remaining work and next gate

Python 3.12 compatibility remains unverified. To check it, create a separate environment with `python3.12 -m venv .venv-py312`, install the pinned requirements, and repeat the CLI, full suite and pip check. Backup validation can enumerate simple paths when the fastest route skips the backup. Large dense graphs with slow backup options have not been benchmarked.

Stages 4–7 remain. Verify the Stage 3 gate before starting Stage 4. The next gate requires seeded reproducibility, shared draws across conditions, availability boundary tests, agreement with deterministic routing when variation is disabled, explicit unserved outcomes, and passing regressions. Interface readiness depends on Stage 7.
