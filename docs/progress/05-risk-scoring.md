# Stage 05 delivery risk and sensitivity snapshot

**Stage 5 of 7, delivery risk scoring and node sensitivity, completed and verified.** Stage 6 has not started. The backend is not ready for interface work.

## Branch and prerequisite

- Worktree `/private/tmp/supply-chain-foundation-backend`, branch `foundation-backend`, Stage 5 base `42c2718e5ec56f27282bb9386a1bc2f64b452cdf`. The worktree started clean. No applicable AGENTS.md was found.
- `git rev-parse HEAD` and `git ls-remote origin refs/heads/foundation-backend` matched at the Stage 4 base. All 50 prerequisite tests passed. The original CLI and pip check also succeeded.

## Stage checklist and changed files

- [x] Score real delivery records. `src/scoring/__init__.py` validates trial collections and calculates mutually exclusive on-time, late, and unserved counts. Each outcome rate divides by all trials. The rates sum to one up to floating-point rounding.
- [x] Compute delivered count, delivered-only mean, and delivered-only linear P95 from end-to-end hours. The deadline is inclusive and both time statistics are null when nothing is delivered. The fragility metric is our defined deadline-risk score, `100 * (late_count + unserved_count) / trial_count`.
- [x] Report stress impact as `100 * (stressed_on_time_rate - baseline_on_time_rate)` and mitigation improvement as `100 * (mitigated_on_time_rate - stressed_on_time_rate)`, in percentage points. `src/domain/__init__.py` derives these changes and delivered count from the validated count fields.
- [x] Measure the impact of disabling one transit node at a time. `src/simulation/monte_carlo.py` reuses the comparison's baseline samples and evaluator for the first `min(settings.trials, 500)` trials. `src/scoring/__init__.py` limits sensitivity to eight transit candidates, defaults to the lowest eight transit IDs, and accepts explicit candidate IDs. The report gives the exact IDs, matching baseline fragility and trial count, and ranks by descending fragility increase with ties broken by ascending node ID.
- [x] Verify formulas and regressions. `tests/test_scoring.py` adds eight tests. `FOUNDATION_PLAN.md`, `summary.md`, and `docs/progress/05-risk-scoring.md` record the interfaces and outcomes.
- Database migration: schema version 2. Stage 5 adds no schema changes. Stage 6 will connect scoring and persist the sensitivity report.

## Verified calculations

- Delivered hours 10, 20, and 30, plus two unserved trials, at a deadline of 20 hours gave counts 2 on time, 1 late, and 2 unserved. Rates were 0.4, 0.2, and 0.4, delivered count was 3, mean was 20 hours, P95 was 29 hours, and fragility was 60.
- On-time rates of 50%, 25%, and 75% gave stress impact of −25 percentage points and mitigation improvement of +50 percentage points.
- On a cut-vertex fixture, candidates (5, 2, 3) across 18 paired trials gave baseline fragility 0. Node 3 increased fragility by 100 points. Nodes 2 and 5 increased it by zero and ranked by ascending ID. A separate coastal run verified that all first 500 sensitivity baseline deliveries exactly matched the first 500 of 520 comparison trials and that default candidates were (2, 3, 4, 5, 6, 7, 8, 9).

## Setup and checks

Ran from the existing worktree with `source .venv/bin/activate`. `python --version` reported Python 3.9.6. No new dependencies were needed.

| Command | Verified result |
| --- | --- |
| `python -m unittest tests.test_scoring -v` | Exit 0, 8 tests passed. |
| `python -m unittest discover -s tests -v` | Exit 0, all 58 tests passed, including all 50 existing tests. |
| `python main.py` | Exit 0. 20 suppliers, 80 routes, 20 nodes and 72 edges. Route `1 -> 20` took 14 transit hours. |
| `python -m pip check` | Exit 0, no broken requirements. The sandbox disabled the pip cache. |
| `git diff --check` | Exit 0, no whitespace errors. |

## Remaining work and next gate

Python 3.12 compatibility and cross-version reproducibility remain unverified. To check Python 3.12, create a separate environment with `python3.12 -m venv .venv-py312`, install the pinned requirements, and repeat the CLI, full suite and pip check.

Stages 6 and 7 remain. Verify the Stage 5 gate before composing the service, CLI, run persistence, replay, and exports. Stage 6 requires a temporary-database CLI workflow exercising every command, reopening saved runs, replaying after a new snapshot is added, and verifying JSON and CSV exports. Preserve sensitivity candidate and trial-budget disclosure in saved and exported comparisons. Interface readiness depends on Stage 7.
