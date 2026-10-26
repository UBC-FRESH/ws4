# Phase close-out report: P62 Harden the hydrology consumer and explicit road/culvert exposure

Phase: P62 Harden the hydrology consumer and explicit road/culvert exposure
Parent issue: #437
Pull request: #468, `feature/p62-hydrology-consumer` into `main`
Evidence head: `0d59e9d` (P62.5), plus the `origin/main` merge `0be35ad`
Report commit: the commit that adds this report. Its CI run is posted on #468.
Date: 2026-10-26
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back
each result.

1. Treat #468 as the single phase pull request.
2. Squash-merge #468 and delete `feature/p62-hydrology-consumer`.
3. Close #449, #450, #451, #452, #453, and #454 with closeout comments that cite
   the merge commit.
4. Close parent issue #437 with a comment that cites the merge commit.
5. Do not launch a real watershed pilot. The next hydrology work is a separate
   phase for schedule-derived road/culvert exposure after a road-state contract
   exists, or FHOPS Phase 15 after its P14 LidarBC phase is ready.

Settings changes, each with its exact command. Each one runs only after its own
approval.

- None.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| P62 is re-scoped away from the blocked Chapman/Seymour pilot. | #437; `notes/design/ws4-hydrology-consumer-hardening.md`; roadmap Phase 62. | Met |
| `hydrology preflight` refuses invalid bundles, blocked readiness, weak policy, unreviewed crosswalks, and incomplete mapping. | `ws4/io/hydrology_preflight.py`; `tests/test_hydrology_preflight.py`; integration fail-closed matrix. | Met |
| An explicit road/culvert exposure table is validated and schedule-bound. | `ws4/io/hydrology_exposure.py`; `ws4.hydrology.exposure.v1`; `tests/test_hydrology_exposure.py`. | Met |
| Screening uses exposure only for the schedule it represents and records identity. | `hydrology screen --exposure`; `tests/test_hydrology_contract.py`; `tests/test_hydrology_integration.py`. | Met |
| Missing declared exposure rows and schedule-hash mismatches refuse. | `screen_schedule_flood_risk`; integration tests. | Met |
| The optimizer refuses fixed exposure rather than reusing it across candidates. | `load_flood_screen_config`; integration test; `notes/backlog.md`. | Met |
| The synthetic path covers validate, readiness, preflight, map, and screen. | `tests/test_hydrology_integration.py`. | Met |
| No real watershed, current flood baseline, flood map, or regulatory result is claimed. | Parent issue, design note, report, and every screen caveat. | Met |
| Dashboard green. | `python scripts/dashboard.py` at `0d59e9d` and after merge `083c143`. | Met |

## 2. Workflow compliance

- Parent issue before the branch: #437 existed before `feature/p62-hydrology-consumer`.
- Branch from `main`: created from `origin/main` at `d51849b`.
- Task branches: none. One phase branch received P62.1-P62.6 and the `origin/main`
  merge `083c143`.
- Commit messages: `P62.1` through `P62.5` are present. The merge commit is the
  `origin/main` integration.
- Child issues: #449-#454 are linked as sub-issues of #437 and remain open until
  the phase merge.
- One phase pull request: #468. No per-task pull requests.
- Roadmap and changelog: updated by each task; P62.6 sets the phase to `pr-open`.
- Approval gates: no merge, tag, release, visibility, or settings change is
  included.

## 3. Gate evidence

At `0d59e9d` (P62.5):

- `pytest -q tests/test_hydrology_integration.py tests/test_hydrology_contract.py tests/test_hydrology_exposure.py tests/test_hydrology_preflight.py --no-cov`: 83 passed.
- `python scripts/dashboard.py`: GREEN (lint, format, types, tests, validator, docs, docstrings).
- `python scripts/check_workflow.py`: 0 errors, 0 warnings.

After merging `origin/main` at `0be35ad`:

- `python scripts/dashboard.py`: GREEN.
- `python scripts/check_workflow.py`: 0 errors, 0 warnings.

The report commit re-runs the dashboard; the result is recorded in the changelog
and on #468.

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 40397685253 | `e319dce` | success | Quality gates, pre-commit parity, clean-checkout contract, green dashboard summary, and notebook outputs all passed. |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| P62 re-scoped from a Chapman/Seymour pilot. | Chapman is closed/data-blocked; Seymour has no reviewed FEMIC bundle. | Kept the phase number, recorded the boundary, and made P62 consumer hardening only. |
| P62 is out of numeric order. | P63, P64, and P65 landed while the P62 branch was active. | Kept P62 reserved by #437; merged `origin/main` as `0be35ad` and kept P62/P63/P64/P65 roadmap and changelog sections. |
| No real watershed screen. | The required reviewed bundle, crosswalk, receptor, gauge, and DEM evidence do not exist. | Used synthetic fixtures only; recorded the data preconditions in the design note. |
| Optimizer-integrated exposure is not implemented. | A fixed table bound to one schedule cannot represent every optimizer candidate. | Refused the config and recorded the follow-up in `notes/backlog.md`. |
| No hydrologist review. | No reviewer record exists. | Preserved the screening-only and review-required caveats. |

## 6. Next phase

Recommended default: do not launch a watershed flood pilot.

The next hydrology step is a separate phase for schedule-derived road/culvert
exposure. It needs:

- a route-state contract that exposes built, used, decommissioned, and culvert
  exposure per schedule;
- reviewed road and culvert evidence;
- a response surface that uses those features; and
- hydrologist review before operational claims.

If FHOPS P14 merges first, FHOPS Phase 15 should consume the same pinned bundle,
mapping, readiness, and policy contracts without re-running FEMIC.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
