# Phase close-out report: P32 Dataset provenance and limitations

Phase: P32, Dataset provenance and limitations
Parent issue: #249
Pull request: not opened yet
Evidence head: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-25
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge the P32 pull request, and delete the branch `feature/p32-provenance`.
2. Close parent issue #249 with a closeout comment that cites the merge commit.
3. Launch P32, Instance provenance adoption: commit the sidecars and a build hook in each
   instance repository, link the limitations page there, and add the provenance check to the
   FreshForge model-build workflow.

Settings changes: none. This phase changes no repository setting, tag, release, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A dataset with a valid sidecar reports `ok`; a missing sidecar remains `unknown`. | `dataset_quality` reads `data_quality.yaml`, reports `provenance: ok`, and keeps the missing case `unknown`. Tests cover both. | Met |
| `ws4 quality --check` fails on a missing or invalid sidecar. | The command writes JSON/Markdown and exits 1 without provenance or when the report is not `ok`. Tests cover both. | Met |
| TSA 46 and TSA 47 reports name inventory vintage, curve provenance, THLB provenance, and unknown imputation/coverage. | Both current matrices carry sidecars; `ws4 quality --check` reports `status: ok` and `provenance_supplied: true`. `notes/reference/gbr-provenance.md` records the values and sources. | Met |
| The limitations page is linked from the provenance output and docs. | `dataset_quality` names `docs/guides/limitations-and-boundaries`; the optimizer reference links it; Sphinx builds. | Met |
| `python scripts/dashboard.py` is green. | Lint, format, types, tests, validator, docs, and docstrings pass at the evidence head. | Met |

## 2. Workflow compliance

- Parent issue before the branch: #249 was created before `feature/p32-provenance`.
- Branch from `main`: the worktree starts at `6a645d9`, the P30.1-P30.2 head.
- The concurrent P30 live-surfaces branch was not touched.
- Commit messages start with task IDs: `P32`.
- Roadmap and changelog in step: P32.1 to P32.3 are checked; the changelog records each.
- Child issues are closed with closeout evidence: #250, #251, and #252.
- Approval gates: the phase opened no pull request until this report; it did not merge, tag, release,
  or change a setting.

## 3. Gate evidence

| Gate | Result at the evidence head |
| --- | --- |
| lint | green |
| format | green |
| types | green |
| tests | green, coverage at or above 90% |
| validator | green |
| docs | green |
| docstrings | green |

## 4. Behaviour smoke

- A valid sidecar on the synthetic dataset reports `status: ok`, `provenance_supplied: true`, and
  `provenance: ok`; a missing sidecar reports `unknown`; an invalid sidecar warns and fails
  `ws4 quality --check`.
- The TSA 46 and TSA 47 current matrices both pass `ws4 quality --check` with `status: ok`.
  The records name 2025 VRI, VDYP-transform curves, predecessor-derived THLB, and explicit null
  imputation/coverage.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The GBR sidecars are applied to the current `runtime/` matrices, which are ignored. | The instance repositories own their compiled outputs; committing them would duplicate generated data. | P32 should track a `config/dataset_quality.yaml` per instance and add a build hook to copy it. |
| The instance docs do not yet link the ws4 limitations page. | The instance repositories are separate and the P32 branch is in ws4. | P32 should add the links in both instance repositories. |
| Imputation share and coverage are `null`. | The source material does not record them. | The report keeps them unknown, as required. |

## 6. Next phase

Goal: make provenance part of the instance build, not a local step.

Tasks:

- P32.1 Add a tracked `config/dataset_quality.yaml` and a build hook in TSA 46 and TSA 47.
- P32.2 Link the model-limitations page from both instance docs.
- P32.3 Add the provenance check to the FreshForge model-build workflow.

Recommended defaults:

- The sidecar is copied beside the compiled `manifest.json` after the matrix build.
- A missing sidecar fails the instance build check; unknown fields stay explicit.
- The values are the ones recorded in `notes/reference/gbr-provenance.md`.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
