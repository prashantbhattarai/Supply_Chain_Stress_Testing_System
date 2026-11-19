# Stage 02 storage snapshot

**Stage 2 of 7, domain, storage, and fixtures, completed and verified.** Stage 3 has not started. The backend is not ready for interface work.

## Branch and prerequisite

- Worktree: `/private/tmp/supply-chain-foundation-backend`. Branch: `foundation-backend`. Stage 2 base: `8c13f541f43b2bd4b1bc8db02868e177b5436a12`. Phase 1 base: `f780cee231a61ba4f80b2194443a5e5c63152180`.
- The worktree started clean at the committed Stage 1 revision with no upstream. No applicable AGENTS.md was found. Origin is the Supply_Chain_Stress_Testing_System GitHub repository.
- Activated the existing environment and reran the Stage 1 gate. The original CLI exited 0 and reported `1 -> 20` at 14 transit hours, all 17 tests passed, and pip check found no broken requirements.
- Ran `git push -u origin HEAD`, `git rev-parse HEAD`, and `git ls-remote origin refs/heads/foundation-backend`. The push created the branch and both SHA checks returned `8c13f541f43b2bd4b1bc8db02868e177b5436a12` before Stage 2 work began.

## Stage checklist

- [x] Verify and publish Stage 1.
- [x] Define frozen, validated domain records and enforce snapshot reference checks.
- [x] Initialize transactional schema version 1 and persist versioned networks, presets, and supplied run results.
- [x] Load and seed validated coastal and tiny fixtures.
- [x] Verify schema, idempotency, round trips, immutability, rejected data, and rollback using temporary databases.
- [x] Run the original CLI, full unittest suite, pip check, and whitespace checks.

## Implemented and changed files

- `src/domain/__init__.py` defines the typed records and validation. IDs are signed SQLite integers. Durations are finite and nonnegative, and reliability and rates have bounded ranges. Canonical ordering makes snapshots and backup sets stable across input ordering.
- `src/domain/fixtures.py`, `data/fixtures/demo.json`, and `data/fixtures/tiny.json` provide an 11-node coastal network and a four-node hand-calculable example. Each includes a port outage, deadline, alternate path, and backup edge stored separately from the base routes.
- `src/storage/__init__.py` and `src/storage/001_initial.sql` implement the repository and initial migration. The schema uses SQLite `user_version = 1` and application ID `0x53435354`. Initialization is repeatable and rejects unrelated databases and unsupported versions. Migration and batch writes roll back together on failure.
- Schema 1 has seven tables: `networks`, `nodes`, `routes`, `scenario_presets`, `scenario_backup_routes`, `runs`, and `run_results`. Composite foreign keys scope network and preset endpoints to a network version. All repository connections enable foreign keys. Repository writes refuse changed data under an existing network or preset key. Use a new version to change a network. Run settings and results are validated JSON payloads tied to the snapshot and saved in one transaction. An external SQL editor can bypass the repository's snapshot immutability rules.
- `tests/test_storage.py` adds 13 tests. `.gitignore` excludes local databases, SQLite sidecars, environments and the default export directory. `FOUNDATION_PLAN.md`, `summary.md`, and `docs/progress/02-storage.md` record the revised contracts and verification.

## Setup and verified commands

Run from the Stage 2 worktree. Activated the existing project environment with `source .venv/bin/activate`. `python -c 'import sqlite3, sys; print(sys.version.split()[0], sqlite3.sqlite_version)'` reported Python 3.9.6 and SQLite 3.51.0. Stage 2 required no dependency installs or changes.

| Command | Actual result |
| --- | --- |
| `python main.py` | Exit 0. 20 suppliers, 80 routes, 80 merged rows, 20 nodes, 72 edges, and the `1 -> 20` path at 14 transit hours. |
| `python -m unittest discover -s tests -v` | Exit 0. 30 tests passed, including all 17 Phase 1 tests and 13 Stage 2 tests. |
| `python -m pip check` | Exit 0. No broken requirements found. The sandbox disabled the pip cache. |
| `git diff --check` | Exit 0 with no whitespace errors. |

Use these commands to initialize and seed the local runtime database. The same repository calls were smoke-tested against a temporary file and returned `coastal-demo` version 1 and `tiny` version 1.

```sh
source .venv/bin/activate
python - <<'PY'
from pathlib import Path

from src.domain.fixtures import bundled_fixtures
from src.storage import SQLiteRepository

repository = SQLiteRepository(Path("var/supply_chain.sqlite3"))
repository.initialize()
repository.seed(bundled_fixtures())
print(repository.list_networks())
PY
```

## Remaining work and next gate

Python 3.12 compatibility remains unverified. When available, create a separate environment with `python3.12 -m venv .venv-py312`, install the pinned requirements, and rerun the CLI, full suite and pip check.

Stages 3–7 remain. Verify the Stage 2 gate before implementing Stage 3 routing, disruption application, and backup validation under deterministic stress. Stage 3 requires exact routes and hour calculations, source readiness counted once, rerouting, no-path behavior, stress retained during mitigation, unchanged snapshots, and a passing regression suite. Simulation, scoring, replay orchestration, and the new CLI remain for later stages. Interface readiness depends on Stage 7.
