# Phase close-out report: P0 Scope and design

Phase: P0 Scope and design
Parent issue: #1
Pull request: #8, `feature/p0-scope-design` into `main`
Evidence head: `6f8b296`, the head that the gates and the CI runs below cover
Report commit: the commit that adds this report. Its CI run is posted on pull request #8.
Date: 2026-10-14
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #8, and delete the branch `feature/p0-scope-design`.
2. Close parent issue #1 with a closeout comment that cites the merge commit.
3. Launch P1 (Contracts and prototype): create its branch, set the phase statuses in `ROADMAP.md`,
   create its child issues as sub-issues of its parent, and start its first task.

Settings changes, each with its exact command. Each one runs only after its own approval.

- None.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| The scope states the problem, users, in-scope and out-of-scope items, and success criteria | `notes/design/ws4-scope.md` (`41d1a76`) | met |
| Each architecture decision is an ADR with context, decision, consequences, and alternatives | `notes/adr/0001` to `notes/adr/0006` (`41d1a76`) | met |
| The architecture note covers the data model, compilation, simulation, optimization, spatial and road subsystems, accounts, CLI, and performance, and names its open questions | `notes/design/ws4-architecture.md` (`41d1a76`) | met |
| `python scripts/dashboard.py` is green on this repository | `OVERALL: GREEN` on all six gates (`d12ebec`) | met |
| The repository names no third-party product in its tracked notes or documentation | `git grep` for the vocabulary returns nothing (`2711022`) | met |
| The optimization and execution architecture is recorded, with its decisions as ADRs | `notes/design/ws4-optimization-stack.md`, `notes/adr/0007` to `notes/adr/0010` (`6f8b296`) | met |

## 2. Workflow compliance

- Parent issue before the branch: **deviation.** The branch `feature/p0-scope-design` was created
  before parent issue #1. The issue was created during the close-out, at the maintainer's direction.
  Recorded in section 5.
- Branch from `main`: merge-base `8c9c3a8` (the initial skeleton commit).
- Commit messages that start with task IDs: 5 of 5 (`d0e2f42` P0.1, `41d1a76` P0.2-P0.4, `2711022`
  P0.6, `d12ebec` P0.5, `6f8b296` P0.7).
- Gates for each commit: section 3.
- Roadmap and changelog in step: updated in `d0e2f42`, `41d1a76`, `2711022`, and `d12ebec`.
- Child issues closed with closeout evidence: #2, #3, #4, #5, #6, #7.
- Approval gates: branch, commits, push, issues, and pull request are allowed within the active phase.
  The maintainer approved each step directly.

## 3. Gate evidence

| Commit | Gates that could run | Result |
| --- | --- | --- |
| `d0e2f42` P0.1 | None installed yet | not run (tooling arrives in P0.5) |
| `41d1a76` P0.2-P0.4 | None installed yet | not run (tooling arrives in P0.5) |
| `2711022` P0.6 | None installed yet | not run (tooling arrives in P0.5) |
| `d12ebec` P0.5 | `python scripts/dashboard.py` | `OVERALL: GREEN` (lint, format, types, tests with the 90% coverage gate, validator, docs) |
| `6f8b296` P0.7 | `python scripts/dashboard.py` | `OVERALL: GREEN` (lint, format, types, tests with the 90% coverage gate, validator, docs) |

The validator reports `0 error(s), 0 warning(s)` on `6f8b296`.

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 38491645108 | `d12ebec` | success | First run for pull request #8. All three jobs pass. |
| 38491937537 | `9020374` | success | Run for the close-out report commit. All three jobs pass. |

The report commit's own run is posted on pull request #8.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The feature branch was created before the parent issue | The work began before the workflow tooling and issues were in place | Parent issue #1 and child issues #2-#7 were created during the close-out; recorded here |
| The early commits have no gate record | The validator and dashboard were installed in P0.5, after the design work | The tooling commit `d12ebec` is green; the design commits are covered by the validator on the current head |
| A local edit to `debug.ipynb` was present in the working tree | An unrelated editor or kernel save | Restored to `HEAD`; notebooks are excluded from ruff |

## 6. Next phase

Phase 1: Contracts and prototype.
Parent issue: to be created at launch.
Branch: `feature/p1-contracts-prototype`.

Goal: fix the data contracts and build the smallest end-to-end prototype that exercises them on
synthetic data.

Tasks and child issues (to create):

- P1.1 Define the compiled-dataset schema and manifest in `docs/`.
- P1.2 Build a prototype that compiles, simulates, and reports on a tiny synthetic landscape.

Acceptance criteria:

- The schema and manifest are documented and validated by a test.
- The prototype compiles a synthetic landscape, replays a schedule, and writes account values.
- `python scripts/dashboard.py` stays green.

Recommended defaults, each with its reason:

- **Prototype format.** Use a tiny synthetic landscape defined in the repository (a handful of
  fragments and blocks). Reason: it exercises the contracts without private data.
- **Schema home.** Put the schema in `docs/` as the RTFM surface, and a machine-readable copy next to
  the code. Reason: one place for readers, one place for the validator.
- **Scope.** Contracts and a prototype only; no optimization. Reason: the optimizer depends on the
  simulator and the dataset being stable first.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
