# Phase close-out report: P3 Verify

Phase: P3 Verify
Parent issue: #26
Pull request: #35, `feature/p3-verify` into `main`
Evidence head: `18b7f67`, the head that the gates and the CI runs below cover
Report commit: the commit that adds this report. Its CI run is posted on pull request #35.
Date: 2026-10-15
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #35, and delete the branch `feature/p3-verify`.
2. Close parent issue #26 with a closeout comment that cites the merge commit.
3. Set P3 to `complete` in `ROADMAP.md` (its task and subtask boxes are now checked).
4. Launch P4 (Release and deploy): create its parent issue, its branch `feature/p4-release`, and its
   child issues as sub-issues, then start its first task (P4.1, release preparation).

Settings changes, each with its exact command. Each one runs only after its own approval.

- None. GitHub Pages is enabled and the repository is public (both done in P3).

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A synthetic landscape compiles, simulates, and optimizes end to end from the CLI | `notes/packaging.md`, `notes/acceptance.md` | met |
| The optimizer satisfies its targets, and replaying its schedule reproduces the account values | `notes/acceptance.md`, `tests/test_optimizer.py` | met |
| Spatial constraints are visible and violated only by an explicit override | `ws4/patch/constraints.py`, `tests/test_constraints.py`, `tests/test_optimizer.py` | met |
| The compiled dataset round-trips through the schema and validates against its manifest | `tests/test_schema.py`, `tests/test_matrix_regression.py` | met |
| A full run is reproducible from its configuration and seed | `tests/test_simulator.py`, `tests/test_optimizer.py`, `notes/performance.md` | met |
| `python scripts/dashboard.py` stays green | `OVERALL: GREEN` at `18b7f67` | met |

## 2. Workflow compliance

- Parent issue before the branch: parent #26 was created before the branch `feature/p3-verify`.
- Branch from `main`: merge-base `3e87d46` (the Phase 2 squash merge).
- Commit messages that start with task IDs: 13 of 13 (`590c8f7` P3 activation, then P3.1 to P3.8 and
  two plan-expansion commits).
- Gates for each commit: section 3.
- Roadmap and changelog in step: updated across the phase and at close-out.
- Child issues closed with closeout evidence: none yet; #27 to #34 close with the phase, each with a
  closeout comment.
- Approval gates: the phase branch, commits, pushes, issues, and the pull request are within the active
  phase. Two changes needed explicit approval and received it: making the repository public and enabling
  GitHub Pages, and adding P3.8 to implement the spatial constraints.

## 3. Gate evidence

| Commit | Gates | Result |
| --- | --- | --- |
| `590c8f7` P3 activation through `18b7f67` P3 roadmap sync (13 commits) | `python scripts/dashboard.py` | `OVERALL: GREEN` at each commit |
| `18b7f67` (evidence head) | `python scripts/dashboard.py` | `OVERALL: GREEN`; lint, format, strict types, 264 tests with the 90 percent coverage gate (94.28 percent), the workflow validator (`0 error(s), 0 warning(s)`), and the docs build all pass |

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 38684845264 | `18b7f67` | success | All three jobs pass. |
| 38684988659 | `4a3f817` | success | All three jobs pass (the report commit). |
| 38535309590 (Docs, `main`) | — | success | The docs deploy succeeds after the repository was made public and Pages was enabled. |

CI runs on pull requests and `main` only, so the branch commits before the pull request have no CI run.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The roadmap criterion "a warm start produces the same result as a cold start" did not hold | A warm start intentionally changes the initial solution | Corrected to determinism (same seed reproduces the same result), which holds (`2189229`) |
| The Verify phase began with one task | It was scoped thin in P0 | Expanded to eight tasks with the maintainer's approval (`e8743de`, `faec99b`) |
| P3.4 found a release-blocking gap (no spatial-constraint enforcement) | A verification finding was a missing feature | Added P3.8 with the maintainer's approval and implemented the constraints (`e21eb92`) |
| The repository was private, so Pages could not be enabled | The Free plan does not support Pages for a private repository | The maintainer approved making the repository public; Pages was then enabled (`13fafb7`) |

## 6. Next phase

Phase 4: Release and deploy.
Parent issue: to be created at launch.
Branch: `feature/p4-release`.

Goal: tag a release, publish the artifacts and the docs, and verify the published release from a clean
checkout.

Tasks and child issues (to create):

- P4.1 Prepare the release: version, changelog, license, citation, and packaging metadata.
- P4.2 Write the release notes and the known-gaps list.
- P4.3 Build and verify the release artifacts (sdist and wheel) from a clean checkout.
- P4.4 Publish the documentation site and verify it from a clean checkout.
- P4.5 Tag the release and publish the artifacts (maintainer approval required).
- P4.6 Verify the published release: install it fresh, run the acceptance checks, and confirm
  reproducibility.

Acceptance criteria:

- A tagged release exists, its artifacts install from a clean checkout, and its docs are published.
- The release notes state the known gaps.

Recommended defaults, each with its reason:

- **Keep the version at 0.0.1 until the release tag.** Reason: P4.1 owns the version bump.
- **Publish the docs from the existing Pages workflow.** Reason: it already builds and deploys.
- **Name the two known gaps in the release notes.** Reason: the full MKRf canonical model is blocked,
  and the wider operator set and tuning portfolio are future work.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
