# Phase close-out report: P1 Contracts and prototype

Phase: P1 Contracts and prototype
Parent issue: #10
Pull request: #14, `feature/p1-contracts-prototype` into `main`
Evidence head: `eb98268`, the head that the gates and the CI runs below cover
Report commit: the commit that adds this report. Its CI run is posted on pull request #14.
Date: 2026-10-14
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #14, and delete the branch `feature/p1-contracts-prototype`.
2. Close parent issue #10 with a closeout comment that cites the merge commit.
3. Launch P2 (Build): create its branch, set the phase statuses in `ROADMAP.md`, create its child issues
   as sub-issues of its parent, and start its first task (P2.1, the ForestModelXML matrix builder).

Settings changes, each with its exact command. Each one runs only after its own approval.

- None.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| The schema and manifest are documented and validated by a test | `docs/reference/compiled-dataset.rst`, `ws4/model/schema.py`, `tests/test_schema.py` (`7b32404`) | met |
| The prototype compiles a synthetic landscape, replays a schedule, and writes account values | `examples/synthetic/`, `ws4/build/compiler.py`, `ws4/sim/engine.py`, `tests/test_prototype.py` (`9b55cb5`) | met |
| The recipe format is an established format, with its validation rules named | `notes/design/ws4-matrix-builder-and-interop.md`, ADR 0011 (`4c0e72a`) | met |
| Both construction paths are recorded, and they meet at one model | ADR 0012 (`4c0e72a`) | met |
| `python scripts/dashboard.py` stays green | `OVERALL: GREEN` on `4c0e72a` | met |

## 2. Workflow compliance

- Parent issue before the branch: parent #10 was created before the branch `feature/p1-contracts-prototype`.
- Branch from `main`: merge-base `386c643` (the Phase 0 squash merge).
- Commit messages that start with task IDs: 4 of 4 (`1eef40d` P1, `7b32404` P1.1, `9b55cb5` P1.2,
  `4c0e72a` P1.3).
- Gates for each commit: section 3.
- Roadmap and changelog in step: updated in `1eef40d`, `7b32404`, `9b55cb5`, and `4c0e72a`.
- Child issues closed with closeout evidence: #11, #12, #13.
- Approval gates: branch, commits, push, issues, and pull request are allowed within the active phase.
  The maintainer approved each step directly.

## 3. Gate evidence

| Commit | Gates | Result |
| --- | --- | --- |
| `1eef40d` P1 activation | `python scripts/dashboard.py` | `OVERALL: GREEN` |
| `7b32404` P1.1 | `python scripts/dashboard.py` | `OVERALL: GREEN` |
| `9b55cb5` P1.2 | `python scripts/dashboard.py` | `OVERALL: GREEN` |
| `4c0e72a` P1.3 | `python scripts/dashboard.py` | `OVERALL: GREEN` |
| `eb98268` P1 CI fix | `python scripts/dashboard.py` | `OVERALL: GREEN` |

The validator reports `0 error(s), 0 warning(s)` on `eb98268`.

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 38510869868 | `ddc83d6` | failure | `Pre-commit parity` failed: the job installed only the dev requirements, so `mypy` and `pytest` could not import `pydantic` and `pandas`. Fixed by `eb98268`. |
| see pull request #14 | `eb98268` | see the pull request | The CI-fix run. |

CI runs on pull requests and on pushes to `main` only, so the branch commits before the pull request
have no CI run. The report commit's own run is posted on pull request #14.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The P1.2 prototype uses a minimal XML recipe format | The prototype needed to exercise the pipeline before the format was fixed | The format was fixed in P1.3 (ADR 0011); the minimal format is superseded in P2, and the matrix contract does not change |
| The branch commits before the pull request have no CI run | CI runs on pull requests and `main` only | The pull request runs the full suite on the report commit |
| The first CI run on the branch failed (`Pre-commit parity`) | The CI jobs installed only the dev requirements, so `mypy` and `pytest` could not import the package's runtime dependencies | `eb98268` adds `python -m pip install -e .` to the CI and docs jobs and adds `[tool.setuptools.packages.find]` |

## 6. Next phase

Phase 2: Build.
Parent issue: to be created at launch.
Branch: `feature/p2-build`.

Goal: implement the agreed scope, one task at a time, on the phase branch.

Tasks and child issues (to create):

- P2.1 Implement the ForestModelXML matrix builder and legacy dataset ingestion.
- P2.2 Implement the simulation engine.
- P2.3 Implement the optimization engine: objective, operators, and one metaheuristic.
- P2.4 Implement the solver core: the shared operator/metaheuristic/tuning/telemetry package.
- P2.5 Implement the parallel and GPU execution substrate.
- P2.6 Implement the math-heuristic layer.
- P2.7 Implement the spatial and road subsystems.
- P2.8 Implement accounts and reporting.
- P2.9 Implement the programmatic model API.

Acceptance criteria:

- Each task lands with tests and documentation, and the dashboard stays green.
- The matrix builder compiles a ForestModelXML recipe and ingests a legacy matrix.
- The simulator reproduces the prototype's account values.

Recommended defaults, each with its reason:

- **Start with P2.1.** The matrix builder is the boundary every other task depends on. Reason: it fixes
  the ingestion side before the engine and the optimizer build on it.
- **Reuse the format contract, not the exporter code.** Default from ADR 0011. Reason: one contract, two
  implementations is cheaper than a divergent copy.
- **Keep the schema version at 0.1 through P2.** Reason: no breaking schema change is planned; bump it
  only if one lands.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
