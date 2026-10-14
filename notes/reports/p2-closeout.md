# Phase close-out report: P2 Build

Phase: P2 Build
Parent issue: #15
Pull request: #25, `feature/p2-build` into `main`
Evidence head: `f22cd6a`, the head that the gates and the CI runs below cover
Report commit: the commit that adds this report. Its CI run is posted on pull request #25.
Date: 2026-10-14
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #25, and delete the branch `feature/p2-build`.
2. Close parent issue #15 with a closeout comment that cites the merge commit.
3. Set P2 to `complete` in `ROADMAP.md` (its task and subtask boxes are now checked; the five deferred
   items are listed in the Phase 2 section and tracked in `notes/backlog.md`).
4. Launch P3 (Verify): create its branch, set the phase statuses in `ROADMAP.md`, create its child
   issues as sub-issues of its parent, and start its first task (P3.1, the acceptance checks).

Settings changes, each with its exact command. Each one runs only after its own approval.

- Enable GitHub Pages so the `Docs` workflow can deploy:
  `gh api -X POST repos/UBC-FRESH/ws4/pages -f build_type=workflow`.
  Reason: the `Docs` workflow's build job passes, but its deploy job fails on every push to `main`
  because Pages is not enabled for the repository.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Each task lands with tests and documentation, and the dashboard stays green | `python scripts/dashboard.py` reports `OVERALL: GREEN`; 198 tests pass with 95.6 percent branch coverage; every commit follows the green-dashboard rule | met |
| The matrix builder compiles a ForestModelXML recipe and ingests a legacy matrix | `ws4/build/compiler.py`, `ws4/build/legacy.py`, `ws4/build/expansion.py`; matches reference compiled matrices exactly on tracks, strata, treatments, blocks, features, products, and `protoaccounts` (nine core variants) | met |
| The simulator reproduces the prototype's account values | `ws4/sim/engine.py`; `tests/test_prototype.py`, `tests/test_simulator.py` | met |
| The optimization engine runs end to end with a report | `ws4/opt/`; `tests/test_optimizer.py`; the C5 sample run in `notes/functional-test.md` | met |
| The spatial and road subsystems route products | `ws4/roads/network.py`; `tests/test_roads.py` | met with a stated limit: core-area rules, edge contrast, destination eligibility, and route cost accounts are deferred |
| The programmatic model API builds or patches a model in memory | `ws4/model/api.py`; `tests/test_api.py` | met |

## 2. Workflow compliance

- Parent issue before the branch: parent #15 was created before the branch `feature/p2-build`.
- Branch from `main`: merge-base `33ac569` (the Phase 1 squash merge).
- Commit messages that start with task IDs: 36 of 37. `5b4788d` ("sync the dev-workflow tooling and CI
  to the latest release") is a tooling commit with no task ID.
- Gates for each commit: section 3.
- Roadmap and changelog in step: updated across the phase and at close-out (`f22cd6a`, and the report
  commit).
- Child issues closed with closeout evidence: none yet; #16 to #24 close with the phase, each with a
  closeout comment.
- Approval gates: branch, commits, push, issues, and pull request are allowed within the active phase.
  The maintainer approved each step directly.

## 3. Gate evidence

| Commit | Gates | Result |
| --- | --- | --- |
| `d1493af` P2 activation through `f22cd6a` P2 roadmap sync (37 commits) | `python scripts/dashboard.py` | `OVERALL: GREEN` at each commit |
| `f22cd6a` (evidence head) | `python scripts/dashboard.py` | `OVERALL: GREEN`; lint, format, strict types, tests with the 90 percent coverage gate, workflow validator (`0 error(s), 0 warning(s)`), and the docs build all pass |

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 38511591182 (Docs, `main`) | P1 merge | failure | The `build` job passes; the `deploy` job fails because GitHub Pages is not enabled. A settings change is named in the recommendation. |
| 38493207193 (Docs, `main`) | P0 merge | failure | Same cause. |
| this pull request's run | report commit | pending | CI runs on pull requests and `main` only, so the branch commits before the pull request have no CI run. |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The account table was first emitted with a signal filter that over-excluded | The account-generation convention was not yet pinned down | `289d784` emits `protoaccounts` for every attribute, groups by the managed state of the producing selects, and preserves a curated `accounts` table; matches the reference exactly on nine core variants |
| The overlay variants do not match | They are a modelling convention for one instance family, not a format feature, and their `output/` recipes are reduced exports that do not correspond to the `tracks_overlay_*` matrices | Recorded as out of scope in `notes/backlog.md` and the Phase 2 section |
| The `Docs` deploy job fails on `main` | GitHub Pages is not enabled | Named as a settings change in the recommendation |
| One commit does not start with a task ID | A tooling sync | Noted here; no task to attribute it to |

## 6. Next phase

Phase 3: Verify.
Parent issue: to be created at launch.
Branch: `feature/p3-verify`.

Goal: show that the build meets its acceptance criteria, and record the evidence in the changelog.

Tasks and child issues (to create):

- P3.1 Run the acceptance checks and record the evidence.

Acceptance criteria:

- The acceptance checks from the roadmap pass, or each failure is recorded with its cause.
- The evidence is in the changelog and the phase report.

Recommended defaults, each with its reason:

- **Start with the end-to-end functional test as the spine.** The C5 sample already exercises build,
  simulate, optimize, and report. Reason: it is the closest thing to a real acceptance run.
- **Keep the deferred P2 items in `notes/backlog.md`.** Reason: they are real gaps and should not be lost.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
