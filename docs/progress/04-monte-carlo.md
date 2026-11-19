# Stage 04 Monte Carlo snapshot

**Stage 4 of 7, Monte Carlo, completed and verified.** Stage 5 has not started. The backend is not ready for interface work.

## Branch and prerequisite

- Worktree `/private/tmp/supply-chain-foundation-backend`, branch `foundation-backend`, Stage 4 base `bd509f977877aa44645ad29171c6b0b4f34abcce`. The worktree started clean. No applicable AGENTS.md was found.
- `git rev-parse HEAD` and `git ls-remote origin refs/heads/foundation-backend` matched at the Stage 3 base. All 40 prerequisite tests passed. The original CLI and pip check also succeeded.

## Stage checklist and changed files

- [x] Enforce input and workload limits before drawing samples. `src/domain/__init__.py` adds `sigma` in [0, 1] and model version `lognormal-pcg64-v1` to the settings contract. The engine rejects unsupported model versions and nonzero legacy jitter. Limits are 25 nodes, 60 directed routes across base and backup combined, and 10,000 trials.
- [x] Generate aligned independent background samples. `src/simulation/monte_carlo.py` derives local streams from the seed and stable node IDs or directed endpoint pairs. It draws Bernoulli availability using each node's reliability and samples mean-preserving lognormal transit hours using `base_hours * exp(sigma*z - sigma*sigma/2)`. Background node availability and edge times are independent. The same entity streams serve all three conditions and preserve global NumPy state.
- [x] Reuse deterministic disruption, backup, and routing logic. `src/graph/scenarios.py` shares scenario preparation and backup addition with the trial engine. The engine sees all sampled conditions at route selection, which assumes optimistic rerouting. It applies the shock after background sampling, and the mitigated graph retains it. The existing evaluator counts source readiness once. Shipment endpoints that fail and routes that disconnect produce absent path and times.
- [x] Expose aligned delivery statuses and replay metadata. The result records the network reference and version, exact run settings, model version, and Python, NumPy, pandas and NetworkX versions. It exposes `on_time`, `late`, and `unserved` sequences using the stored deadline.
- [x] Verify deterministic equivalence, boundary reliability, shared draws, same-seed runs, evaluation-order and insertion-order independence, unchanged global state, and backup monotonicity. `tests/test_monte_carlo.py` adds 10 tests. `FOUNDATION_PLAN.md`, `summary.md`, and `docs/progress/04-monte-carlo.md` document the updated contract.
- Database migration: schema version 2. No migration was needed. The existing settings payload can still read legacy records, and the service layer will persist full replay metadata in Stage 6.

## Setup and checks

Ran from the existing worktree with `source .venv/bin/activate`. No new dependencies were needed. The command `python -c 'import networkx, numpy, pandas, sqlite3, sys; print(sys.version.split()[0], numpy.__version__, pandas.__version__, networkx.__version__, sqlite3.sqlite_version)'` reported `3.9.6 2.0.2 2.3.3 3.2.1 3.51.0`.

| Command | Verified result |
| --- | --- |
| `python -m unittest tests.test_monte_carlo -v` | Exit 0, 10 tests passed. |
| `python -m unittest discover -s tests -v` | Exit 0, all 50 tests passed, including all 40 earlier tests. |
| `python main.py` | Exit 0. 20 suppliers, 80 routes, 20 nodes and 72 edges. Route `1 -> 20` took 14 transit hours. |
| `python -m pip check` | Exit 0, no broken requirements. The sandbox disabled the pip cache. |
| `git diff --check` | Exit 0, no whitespace errors. |

A smoke run at the trial and sigma limits completed with 10,000 statuses for each condition:

```sh
python - <<'PY'
from src.domain import RunSettings
from src.domain.fixtures import bundled_fixtures
from src.simulation.monte_carlo import simulate

network, preset = bundled_fixtures()[0]
result = simulate(network, RunSettings(preset.shipment, preset.scenario, 10000, 42, sigma=1))
print({condition: len(statuses) for condition, statuses in result.statuses.items()})
PY
```

## Remaining work and next gate

Python 3.12 compatibility and reproducibility across dependency versions remain unverified. To verify Python 3.12, create a separate environment with `python3.12 -m venv .venv-py312`, install the pinned requirements, and repeat the CLI, full suite and pip check. The smoke run used the coastal fixture. It did not benchmark the densest graph allowed by the caps.

Stages 5–7 remain. Verify the Stage 4 gate before implementing Stage 5 risk metrics and criticality. Its gate requires hand-checkable mixed, all-delivered, and all-unserved results, inclusive deadline handling, delivered-only percentile checks, tied criticality ranking, and passing regressions. Interface readiness depends on Stage 7.
