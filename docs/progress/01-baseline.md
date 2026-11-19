# Stage 01 baseline snapshot

**Stage 1 of 7, baseline and contracts, completed and verified.** Stage 2 has not started. The backend is not ready for interface work.

## Starting state and checkout

- Audit date: 2026-11-19. No applicable AGENTS.md was found. Reviewed the working tree, remote configuration, refs, commit history, tracked README, source, and tests.
- Original worktree: `/Users/prashantbhattarai/supply_chain_stress_tester` on `phase1-graph-foundation`. The five modified tracked files were `.gitignore`, `requirements.txt`, `src/cleaning/day01.setup.py`, `src/data_generation/day01.setup.py`, and `src/data_generation/day03_numpy.py`. Untracked files included dashboard, deployment, and simulation work. All were kept in that worktree.
- `git fetch origin` succeeded with permission to write Git metadata. Fetched `origin/main` and local `main` were at `29131a1`. Local and remote Phase 1 were at `f780cee231a61ba4f80b2194443a5e5c63152180`. No newer branch containing the Phase 1 commit or existing `foundation-backend` branch was present.
- `gh pr view 1 --json state,headRefName,headRefOid,baseRefName,url` verified that PR #1 was open from `phase1-graph-foundation` at that commit into `main`. [PR #1](https://github.com/prashantbhattarai/Supply_Chain_Stress_Testing_System/pull/1)
- Stage worktree: `/private/tmp/supply-chain-foundation-backend`, branch `foundation-backend`, base `f780cee231a61ba4f80b2194443a5e5c63152180`. Created with `git worktree add -b foundation-backend /private/tmp/supply-chain-foundation-backend f780cee`.

## Stage checklist and deliverables

- [x] Audit the original checkout and verify GitHub refs and PR status.
- [x] Isolate the backend branch and preserve existing local work.
- [x] Install pinned requirements in a project virtual environment.
- [x] Verify the original CLI, existing unit tests, and dependency consistency.
- [x] Document the seven stages, model semantics, typed module boundaries, CLI contract, and completion gates.

Changed files are `FOUNDATION_PLAN.md`, this `summary.md`, and `docs/progress/01-baseline.md`. Stage 1 establishes contracts. The verified executable baseline generates repeatable supplier and route data, builds a directed graph with duplicate routes collapsed, and reports the Dijkstra path and transit hours. Tracked `src/simulation/monte_carlo.py` contains imports and a comment. **Database migration/schema version:** no database or migration exists at this stage. Stage 2 will introduce schema version 1.

## Setup and check results

Run from the stage worktree. Python 3.12 was not found on PATH or in the checked installation locations. Used Python 3.9.6 with SQLite 3.51.0. Existing virtual environments were preserved.

| Exact command | Actual result |
| --- | --- |
| `python3 -m venv .venv` | Created the worktree environment. Its local `.venv/.gitignore` keeps environment files out of Git. |
| `.venv/bin/python -m pip install -r requirements.txt` | Initial sandboxed attempt failed resolving the index. Retried with network approval and installed all 17 pinned packages. |
| `.venv/bin/python -c 'import sqlite3, sys; print(sys.version.split()[0], sqlite3.sqlite_version)'` | Reported `3.9.6 3.51.0`. |
| `.venv/bin/python main.py` | Exit 0. 20 suppliers, 80 routes, 80 merged rows, 20 graph nodes, 72 edges, status `ok`, path `1 -> 20`, 14 transit hours. |
| `.venv/bin/python -m unittest discover -s tests -v` | Exit 0. All 17 tests passed. |
| `.venv/bin/python -m pip check` | Exit 0. No broken requirements found. Pip reported that its cache directory was unavailable in the sandbox. |

The CLI, tests, and pip check also passed initially using the original checkout's virtual environment against the isolated sources. An offline exact-pin probe of that environment stopped at `packaging==25.0`. The successful fresh worktree install and checks are the completion evidence.

## Remaining work and next gate

Python 3.12 compatibility is unverified. Once available, create a separate environment using `python3.12 -m venv .venv-py312`, install the pins using `.venv-py312/bin/python -m pip install -r requirements.txt`, and rerun the CLI, unittest suite, and pip check with that interpreter.

Stages 2–7 remain. Begin Stage 2 by verifying the Stage 1 gate and then implementing domain validation, the versioned demo fixture, and SQLite network storage. Stage 2 requires fresh and repeated initialization, idempotent seeding, immutable snapshots that round-trip after reconnect, atomic rejection of invalid writes, and passing Phase 1 regressions. Interface readiness depends on Stage 7.
