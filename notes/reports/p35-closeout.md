# Phase close-out report: P35 Instance provenance adoption

Phase: P35, Instance provenance adoption
Parent issue: #267
Pull request: not opened yet (ws4 tracker/docs)
Companion pull requests: femic-tsa46-instance #25, femic-tsa47-instance #26
Date: 2026-10-25
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge the ws4 tracker/docs pull request.
2. Close parent issue #267 with a closeout comment that cites both companion merge commits.
3. Launch P36, FreshForge provenance provider: add the apply/check step to the workflow
   provider so the FreshForge lane enforces provenance as well as the shell build.

Settings changes: none. This phase changes no repository setting, tag, release, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A fresh build copies `data_quality.yaml` beside the matrix and passes the quality check. | Both build scripts call `scripts/apply_dataset_quality.py` after `ws4 build`/`validate`; the script copies the sidecar and calls `ws4 quality --check`. | Met |
| Both instance docs link the limitations page. | TSA 46 and TSA 47 `docs/model-build.rst` name the page and the VDYP/THLB caveats. | Met |
| The build exits non-zero when provenance is missing or invalid. | `apply_dataset_quality.py --check` returns 1 on a non-ok report; tests cover pass/fail. | Met |
| Each instance dashboard is green. | TSA 46 and TSA 47 dashboards pass lint, format, types, tests with coverage, validator, and docs. | Met |

## 2. Workflow compliance

- Parent issue #267 and child issues #268–#270 were created before the instance branches.
- Instance branches: `feature/p35-provenance` in both instance repositories.
- Companion PRs: femic-tsa46-instance #25, femic-tsa47-instance #26.
- Commit messages start with `P35`.
- Child issues are closed with closeout evidence.
- The concurrent P33/P34 ws4 phases were not touched.

## 3. Gate evidence

| Gate | Result |
| --- | --- |
| TSA 46 dashboard | green |
| TSA 47 dashboard | green |
| TSA 46 quality check | `provenance: ok` |
| TSA 47 quality check | `provenance: ok` |
| ws4 tracker/docs | to be run before the PR |

## 4. Merge evidence

- femic-tsa46-instance #25 merged as `2c2c809`.
- femic-tsa47-instance #26 merged as `2f1041d`.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The FreshForge provider hook is not added. | The workflow provider is outside the shell build and needs a new provider contract. | P36 should add it; the shell build is the documented reproducible lane for now. |
| The tracked sidecar duplicates the P32 note values. | The instance repository owns the dataset, so the sidecar must travel with its build. | Keep `notes/reference/gbr-provenance.md` as the cross-repo evidence record. |

## 6. Next phase

Goal: enforce provenance in the workflow lane, not only the shell script.

Tasks:

- P36.1 Add an apply/check provider step to the FreshForge model-build workflow.
- P36.2 Fail the workflow when the sidecar is missing or invalid.
- P36.3 Record the sidecar and check result in the workflow run manifest.

Recommended defaults:

- The provider calls the same instance script, not a second implementation.
- Unknown fields remain explicit; the workflow does not invent values.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
