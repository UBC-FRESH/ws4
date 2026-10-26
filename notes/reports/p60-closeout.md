# Phase close-out report: P60 Harden hydrology use with validation evidence

Phase: P60 Harden hydrology use with validation evidence
Parent issue: #415
Pull request: #428, `feature/p60-closeout` into `main`
Evidence head: `2bceea0` (P60.2), plus the report commit
Report commit: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-26
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Close #422 and #424 as superseded by the single phase pull request #428.
2. Squash-merge #428 and delete `feature/p60-closeout` and the two superseded task branches.
3. Close child issues #416, #423, and #426 with closeout comments that cite the merge commit.
4. Close parent issue #415 with a comment that cites the merge commit and the next recommendation.
5. Launch the next bounded phase only after approval: a public-watershed pilot and tail-check remediation, or FHOPS Phase 15 if its P14 LidarBC phase is ready first.

Merge command, after final CI is green:

```shell
gh pr merge 428 --squash --delete-branch
```

Settings changes, each with its exact command. Each one runs only after its own approval.

- None.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Missing validation evidence is reported, not treated as approval. | `assess_femic_hydrology_readiness`; `not_available` tests. | Met |
| Provisional evidence is explicit. | `provisional` state and warnings; model-card review status. | Met |
| Tail-check failures block. | `blocked` state; `enforce_hydrology_readiness`; screen/optimizer tests. | Met |
| A reviewed, clean model card is ready. | `ready` state test with `reviewed` and a recorded review. | Met |
| Policy gates screening and optimizer use. | `allow_provisional`, `require_reviewed`, `require_ready`; screen CLI and `FloodRiskModel` construction. | Met |
| No FEMIC re-run or regulatory claim. | No producer execution; every artifact/report carries the screening-only boundary. | Met |
| Dashboard green. | Green at `2bceea0`; report commit re-runs the dashboard. | Met |

## 2. Workflow compliance

- Parent issue before task branches: #415 was created before the P60 task branches.
- Original phase number was P59; it collided with the LiDAR UI PR #425. The phase and task issues were renumbered to P60 before closeout.
- Branch base: P60.1 was based on `main`; P60.2 was stacked on P60.1; this closeout branch is stacked on P60.2.
- Commit messages: `P60.1`, `P60.2`, and `P60.3` are present; older commit hashes retain their original branch history.
- Roadmap and changelog: P60.3 sets the phase to `pr-open`.
- Approval gates: no merge, tag, release, visibility, or settings change is included.

## 3. Gate evidence

At `2bceea0` (P60.2):

- `pytest -q tests/test_hydrology_contract.py --no-cov`: 51 passed.
- `python scripts/dashboard.py`: GREEN (lint, format, types, 121.59 s tests,
  validator, docs, docstrings).
- `python scripts/check_workflow.py`: 0 errors, 0 warnings.
- Sphinx `-W`: passed.

The report commit re-runs the dashboard; the result is recorded in the
changelog and the PR.

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| pending | report commit | not yet run | CI runs on #428. |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Phase number changed from P59 to P60. | PR #425 (`feature/p59-lidar-ui`) claimed P59 for LiDAR web UI while this phase was in progress. | Renumbered issues, roadmap, docs, and task titles to P60; kept old branch names only until closeout deletion. |
| Two task PRs instead of one phase PR. | P60.1 and P60.2 were queued separately before approval. | Consolidated into #428; #422 and #424 are superseded. |
| No public-watershed pilot. | No reviewed public crosswalk/domain with FEMIC ledger units is available. | Follow-up pilot; do not infer a watershed. |
| No hydrologist review. | No reviewer record exists. | Preserve `not_reviewed`; require reviewed evidence for operational use. |
| No FHOPS integration. | FHOPS P14 is still its LidarBC phase. | FHOPS Phase 15 after P14. |
| No independent WS4 tail-check fitting. | WS4 consumes producer evidence; it does not refit distributions. | Keep producer tail-check metadata authoritative; follow-up remediation if a producer fit is blocked. |

## 6. Next phase

Recommended default: a bounded public-watershed pilot and tail-check remediation
phase. It should obtain a reviewed public crosswalk/domain with FEMIC ledger
units, exercise `require_reviewed`/`require_ready`, measure whole-schedule
screening cost, and require a hydrologist-approved model card before operational
claims.

If FHOPS P14 merges first, FHOPS Phase 15 should consume the same pinned bundle,
mapping, readiness, and policy contracts.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
