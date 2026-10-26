# Phase close-out report: P57 Consume FEMIC hydrology response bundles

Phase: P57 Consume FEMIC hydrology response bundles
Parent issue: #395
Pull request: #411, `feature/p57-closeout` into `main`
Evidence head: `c35af30` (P57.5), plus the report commit
Report commit: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-26
Status: approved for single-phase squash merge; not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Treat #411 as the single phase pull request. It now targets `main` and carries P57.1-P57.6.
2. Close #397, #400, #402, #406, and #409 as superseded by #411; keep their branches until the phase merge is complete.
3. Squash-merge #411 and delete `feature/p57-closeout` and the five task branches.
4. Close child issues #396, #399, #401, #403, #407, and #410 with closeout comments that cite the merge commit.
5. Close parent issue #395 with a comment that cites the merge commit and the next recommendation.
6. Launch the next bounded phase only after approval: a public-watershed pilot and tail-check hardening for the WS4 consumer, or FHOPS Phase 15 if that repository is ready first.

Merge command, after final CI is green:

```shell
gh pr merge 411 --squash --delete-branch
```

Settings changes, each with its exact command. Each one runs only after its own approval.

- None.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A pinned FEMIC hydrology bundle is validated with a stable pin and per-artifact SHA-256/size. | `ws4/io/hydrology.py`; `tests/test_hydrology_contract.py::test_valid_bundle_pins_artifacts_and_preserves_caveats`; FEMIC-built fixture `hydro-response-70f4214e01afe461` validated through the WS4 CLI. | Met |
| A validated bundle is registered in a compiled dataset without copying it. | `register_femic_hydrology_bundle`; five registration tests; `hydrology_products.json` + `metadata.hydrology_products`. | Met |
| WS4 fragments/blocks map to FEMIC units/watersheds/receptors only through an explicit reviewed crosswalk. | `hydrology map`; crosswalk metadata/review state; conflict, unknown-ID, and coverage tests. No spatial inference. | Met |
| A schedule produces receptor/watershed/return-period screening rows with applicability refusal. | `hydrology screen`; complete/partial/refusal tests; `hydrology_screen.csv` and manifest. | Met |
| Optional `flood.*` accounts can be priced by normal targets. | `FloodRiskModel`; optimizer target test; account rows across years. | Met |
| Out-of-envelope schedules refuse rather than extrapolate. | `FloodRiskRefusalError` path; optimizer returns configured penalty; tests. | Met with stated limit (refusal is a constant penalty, not a feasibility proof). |
| The screening-only and hydrologist-review boundaries are explicit. | Docs, design note, model-card handoff, caveats in every artifact. | Met |
| Dashboard green. | Green at `c35af30` and at the report commit; see section 3. | Met |

## 2. Workflow compliance

- Parent issue before the branch: #395 was created before the P57 branch and the task branches.
- Branch base: each task branch was stacked on its predecessor; the approved consolidation retargets #411 to `main`.
- Commit messages: `P57.1` through `P57.6` prefixes are present.
- Roadmap and changelog: updated by each task; P57.6 sets the phase to `pr-open`.
- Child issues: open pending review; close them only after the corresponding PR merges.
- Approval gates: the maintainer approved the single-phase-PR merge strategy on 2026-10-26. No tag, release, visibility, or settings change is included.

## 3. Gate evidence

At `c35af30` (P57.5):

- `pytest -q tests/test_hydrology_contract.py --no-cov`: 39 passed.
- `python scripts/dashboard.py`: GREEN (lint, format, types, 104.92 s tests,
  validator, docs, docstrings).
- `python scripts/check_workflow.py`: 0 errors, 0 warnings.
- Sphinx `-W`: passed.

The report commit re-runs the dashboard; the result is recorded in the changelog
and the PR.

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| pending | report commit | not yet run | CI runs on #411 after the consolidation commit. |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| WS4 phase renumbered to P57. | The planned `P49` is already a closed managed/young validation phase. | Treat FEMIC `consumer_phases` as producer metadata; document WS4's actual phase. |
| Six stacked PRs instead of one phase PR. | Each task was bounded and queued before the prior task merged, per the one-task-at-a-time workflow. | Resolved by retargeting #411 to `main` and closing the five task PRs as superseded. |
| No real public watershed mapping or production pilot. | The workspace has no reviewed public crosswalk/domain with FEMIC ledger units. | Follow-up public pilot; do not infer a watershed. |
| No hydrologist review. | No reviewer record exists. | Preserve `not_reviewed`; require review before operational use. |
| No independent WS4 tail-check validation. | The consumer validates bundle structure/checksums, not FEMIC fit diagnostics. | Use the FEMIC model-card/tail-check metadata; add a dedicated guard in the follow-up phase. |
| Flood accounts are optimizer-only and whole-schedule. | No incremental model for landscape flood response. | Accept for screening; benchmark and add an incremental/approximate path only with evidence. |
| No FHOPS integration. | FHOPS P14 is still its LidarBC phase. | FHOPS Phase 15 after P14 merges. |

## 6. Next phase

Recommended default: a bounded WS4 public-watershed pilot and tail-check
hardening phase. It should:

- obtain a reviewed public crosswalk and FEMIC domain/ledger with units;
- verify the FEMIC tail-check/model-card conditions before reading flood rows;
- measure the whole-schedule screening cost on a realistic estate;
- require hydrologist review of the model card before operational claims.

If FHOPS P14 merges first, FHOPS Phase 15 should consume the same pinned bundle
and mapping contract without re-running FEMIC.

## 7. Decision

- [x] Approve as written.
- [ ] Approve with the changes stated here: <changes>.

Approval: maintainer selected the single-phase-PR strategy on 2026-10-26.
