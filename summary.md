# Backend foundation status

**Stage 6 of 7, persistent backend workflow, completed and verified.** Stage 7 and interface work have not started.

## Branch and prerequisite

- Worktree `/private/tmp/supply-chain-foundation-backend`, branch `foundation-backend`, Stage 6 base `d8ebd76ca0a2d0e86d294fd311e5f344121da10a`. The worktree started clean and no applicable AGENTS.md was found.
- `git rev-parse HEAD` and `git ls-remote origin refs/heads/foundation-backend` matched at the Stage 5 base. All 58 prerequisite tests passed, along with the original CLI and pip check.

## Stage checklist and changed files

- [x] Compose the service in `src/pipeline.py`. It resolves a saved network and preset, applies explicit overrides, simulates the three conditions, scores trials, times comparison and sensitivity separately, and persists a typed result. Replay verifies exact trials, metrics and criticality using stored inputs.
- [x] Store complete runs atomically. `src/storage/003_run_details.sql` migrates schema 2 to **schema 3**, adding validated preset sigma and a `run_details` table tied to `run_results`. `src/storage/__init__.py` and `src/storage/run_details.py` persist and decode the complete snapshot, SHA-256 fingerprint, scenario settings, seed, runtime and code provenance, sensitivity, and all trial outcomes. Older summary-only runs remain readable. The full-run rollback test injects failure on the final insert and checks that all three run tables stay empty.
- [x] Add typed records in `src/domain/__init__.py` and reuse them in `src/scoring/__init__.py`. `src/domain/fixtures.py` and `data/fixtures/{demo,tiny}.json` validate and expose the saved volatility default of 0.15.
- [x] Implement all seven CLI commands in `src/cli.py`. `src/utils/export.py` writes `summary.csv`, `trials.csv`, and strict `metadata.json` with run settings, units, and sensitivity disclosure. Existing export files require `--overwrite`.
- [x] Test subprocess reopen, replay, rollback, saved snapshot interpretation after adding a new version, invalid requests, version mismatch, fingerprint corruption, and export fidelity. `tests/test_backend_workflow.py` adds six tests and `tests/test_storage.py` verifies the new schema version.
- [x] Update `README.md`, `FOUNDATION_PLAN.md`, `summary.md`, and `docs/progress/06-backend-workflow.md`.

## Verified temporary database run

Commands ran under `source .venv/bin/activate` from the stage worktree. The temp directory was created with `mktemp -d /private/tmp/supply-stage6.XXXXXX`. Each CLI invocation opened and closed SQLite independently.

```sh
db=/private/tmp/supply-stage6.uDyrGG/supply_chain.sqlite3
python -m src.cli --db "$db" init-db
python -m src.cli --db "$db" seed-demo
python -m src.cli --db "$db" list-networks
python -m src.cli --db "$db" compare --network demo-v1 --preset port-outage --seed 42 --trials 2000
python -m src.cli --db "$db" show-run --run-id 93935b84-822d-44b3-9ab9-7ef2eb282860
python -m src.cli --db "$db" replay-run --run-id 93935b84-822d-44b3-9ab9-7ef2eb282860
python -m src.cli --db "$db" export-run --run-id 93935b84-822d-44b3-9ab9-7ef2eb282860 --output-dir /private/tmp/supply-stage6.uDyrGG/export
```

All workflow commands exited 0. Listing showed `coastal-demo-v1` (alias `demo-v1`) and `tiny-v1`. Reopened output matched the original comparison exactly. Replay verified the run, and the export had 3 summary rows and 6,000 trial rows, excluding headers.

The run used Python 3.9.6, NumPy 2.0.2, pandas 2.3.3, NetworkX 3.2.1, and model `lognormal-pcg64-v1`. Its code revision was the Stage 5 base, with `code_dirty=true` because this check ran before the Stage 6 commit. The shipment was 1 → 10 at a 50-hour deadline and sigma 0.15. Comparison took **0.387382 s**, and criticality took **0.271008 s**. These timings exclude persistence and CLI startup.

| Condition | On time | Late | Unserved | Fragility | Delivered mean | Delivered P95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | 1747 | 144 | 109 | 12.65 | 43.621 h | 61.885 h |
| Stressed | 0 | 1797 | 203 | 100.00 | 62.959 h | 68.182 h |
| Mitigated | 1824 | 74 | 102 | 8.80 | 45.505 h | 49.319 h |

Stress impact was −87.35 percentage points and mitigation improvement was +91.20 percentage points. Sensitivity used candidate IDs 2 through 9 and 500 trials. Matching baseline fragility was 14.80. Nodes 3, 4, 5, and 9 tied at +85.20 points in ascending ID order. Nodes 2, 6, 7, and 8 tied at zero.

## Regression checks

| Command | Verified result |
| --- | --- |
| `python -m unittest tests.test_backend_workflow -v` | Exit 0, 6 tests passed. |
| `python -m unittest discover -s tests -v` | Exit 0, all 64 tests passed. |
| `python main.py` | Exit 0, route `1 -> 20` took 14 transit hours. |
| `python -m pip check` | Exit 0, no broken requirements. The sandbox disabled the pip cache. |
| `git diff --check` | Exit 0, no whitespace errors. |

## Remaining work and next gate

Python 3.12 and cross-version reproducibility remain unverified. Replay reports incompatible versions and flags differing or dirty code provenance. A Git SHA and dirty flag cannot reconstruct uncommitted source. To check Python 3.12, create `python3.12 -m venv .venv-py312`, install the pinned requirements, and rerun the legacy CLI, backend workflow, full suite, and pip check.

Stage 7 remains. Its gate requires a fresh environment, full tests and dependency checks, both entry points, and a documented migration, replay, export and handoff workflow. The backend is not yet ready for interface work under the foundation plan.
