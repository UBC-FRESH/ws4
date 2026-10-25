# Phase close-out report: P37 FreshForge provenance gate

Phase: P37, FreshForge provenance gate
Parent issue: #278
Pull request: this closeout/docs PR
Companion pull requests: femic #346, femic-tsa46-instance #27, femic-tsa47-instance #28
Date: 2026-10-25
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge this closeout/docs pull request.
2. Close parent issue #278 with a closeout comment that cites the merge commits.
3. Launch P38, Instance FreshForge provider execution: implement the `tsa46.ws4.*` and
   `tsa47.ws4.*` provider packages so the workflow nodes run, then execute the workflow end to end.

Settings changes: none. This phase changes no repository setting, tag, release, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| `ws4 quality --sidecar PATH --check` installs the sidecar and gates the report. | P37.1; test covers the install-and-check path. | Met |
| `femic.ws4_quality` builds the install/check command and is covered by a provider test. | P37.2; integration test asserts the exact command and metadata. | Met |
| Both instance workflows add the node after validation and name the gate in docs. | P37.3; both workflows and model-build pages updated. | Met |
| Dashboards are green. | ws4, femic guard/package checks, and both instance dashboards pass. | Met |

## 2. Workflow compliance

- Parent issue #278 and children #279–#281 were created before the branches.
- Branches: `feature/p37-provenance-gate` in ws4, femic, and both instances.
- Child issues are closed with closeout evidence.
- P36 was already taken by workflow conformance; this work uses P37.

## 3. Merge evidence

- ws4 P37.1: `86f7ec1`.
- femic P37.2: `e3251e9`.
- femic-tsa46-instance P37.3: `03dc620`.
- femic-tsa47-instance P37.3: `2e7b29d`.

## 4. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The instance workflow still references `tsa46.ws4.*` / `tsa47.ws4.*` providers that are not installed. | Those provider packages pre-date this phase and are outside the FEMIC provider. | P38 should implement and test them; the new `femic.ws4_quality` node is runnable once the build/validate provider chain exists. |
| The workflow gate was not executed end to end. | The missing instance provider chain blocks a full workflow run. | P38 owns the end-to-end execution and CI evidence. |

## 5. Next phase

Goal: make the instance FreshForge graph executable.

Tasks:

- P38.1 Implement the `tsa46.ws4.*` and `tsa47.ws4.*` providers (build, validate, schedule, simulate).
- P38.2 Run both workflows end to end with the provenance gate.
- P38.3 Add provider/CI evidence and document the run command.

Recommended defaults:

- Providers call the same scripts used by the shell build.
- The provenance node remains after validation.
- No new model logic in the provider layer.

## 6. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
