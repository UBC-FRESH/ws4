# Phase close-out report: P39 Instance FreshForge provider execution

Phase: P39, Instance FreshForge provider execution
Parent issue: #287
Pull request: this docs/tracker PR
Companion pull requests: femic-tsa46-instance #28, femic-tsa47-instance #29
Date: 2026-10-25
Status: merged and closed on 2026-10-25 as `8f77a9a`.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge this docs/tracker pull request.
2. Close parent issue #287 with a closeout comment that cites the companion merges.
3. Launch P39, Bounded workflow execution smoke: run the full provider graph on a small fixture
   or a bounded c5 run and record the artifacts.

Settings changes: none. This phase changes no repository setting, tag, release, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Each instance exposes its `tsaXX.ws4` provider through an entry point. | `pyproject.toml` entry points and provider tests in both instances. | Met |
| The provider builds the expected commands for every workflow node. | Tests cover build, validate, baseline schedule, and simulate. | Met |
| FreshForge validation resolves every node in both workflows. | Local validation with the FEMIC provider: 0 diagnostics for both workflows. | Met |
| `python scripts/dashboard.py` is green in both instances. | TSA 46 and TSA 47 dashboards pass every gate. | Met |

## 2. Workflow compliance

- Parent issue #287 and children #288–#290 were created before the branches.
- Instance branches: `feature/p38-provider`.
- Companion PRs: femic-tsa46-instance #28, femic-tsa47-instance #29.
- Commit messages start with `P39`.

## 3. Merge evidence

- femic-tsa46-instance #28: `3b89fa9`.
- femic-tsa47-instance #29: `6ea2dbe`.

## 4. Behaviour

Each provider exposes:

- `build_dataset`: `ws4 build`.
- `validate_dataset`: `ws4 validate`.
- `build_baseline_schedule`: `scripts/build_baseline_schedule.py`.
- `simulate`: `ws4 simulate`.

The provider is packaged under `src/tsaXX_workflow`, discovered through
`freshforge.providers`, and the model-build docs name the `freshforge validate` command.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The full graph was validated, not executed against a real matrix. | A full run needs the upstream bundle and a bounded runtime lane. | P39 owns the bounded execution smoke. |
| FreshForge is optional in instance CI. | The CI environment does not install the optional `freshforge` extra. | Provider tests use `importorskip`; provider execution is verified locally and documented. |

## 6. Next phase

Goal: execute the graph, not only validate it.

Tasks:

- P39.1 Run the TSA 46 and TSA 47 workflows on a bounded fixture or c5 dataset.
- P39.2 Record the provider commands, artifacts, and provenance gate result.
- P39.3 Add a repeatable smoke command and CI evidence where feasible.

Recommended defaults:

- Bound the run with a small block subset or a prebuilt matrix.
- Keep the full inventory out of CI.
- Fail the smoke on a non-zero provider node.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
