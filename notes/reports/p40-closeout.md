# Phase close-out report: P40 Bounded provider workflow execution

Phase: P40, Bounded provider workflow execution
Parent issue: #297
Pull request: this docs/tracker PR
Companion pull requests: femic-tsa46-instance #29, femic-tsa47-instance #30
Date: 2026-10-25
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge this docs/tracker pull request.
2. Close parent issue #297 with a closeout comment that cites the companion merges.
3. Launch P41, Provider smoke in CI: install the pinned FEMIC/FreshForge provider set in the
   instance CI and run the dry-run/real smoke on a small fixture.

Settings changes: none. This phase changes no repository setting, tag, release, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Both smoke graphs execute every selected node successfully. | TSA 46 and TSA 47 runs both report four `success` nodes. | Met |
| The provenance node passes on the existing sidecar. | `apply_dataset_quality` success in both runs. | Met |
| The schedule and one-year simulation artifacts exist. | `smoke/baseline.csv` and `smoke/run/account_values.csv` exist for both. | Met |
| The evidence JSON names the commands, statuses, and artifacts. | `runtime/smoke/evidence.json` for both runs. | Met |

## 2. Workflow compliance

- Parent issue #297 and children #298–#300 were created before the branches.
- Instance branches: `feature/p40-smoke`.
- Companion PRs: femic-tsa46-instance #29, femic-tsa47-instance #30.
- Commit messages start with `P40`.

## 3. Merge evidence

- femic-tsa46-instance #29: `b351103`.
- femic-tsa47-instance #30: `80dcbd8`.

## 4. Smoke evidence

TSA 46:

- Four nodes success.
- `smoke/baseline.csv`: 1,930,119 bytes.
- `smoke/run/account_values.csv`: 4,636 bytes.

TSA 47:

- Four nodes success.
- `smoke/baseline.csv`: 804,242 bytes.
- `smoke/run/account_values.csv`: 4,085 bytes.

The run starts at `validate_dataset` on the existing matrix and does not rebuild the inventory or
run the upstream compile/export nodes.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The build node is not in the smoke graph. | It would rebuild the full matrix; P38 unit tests cover its command. | P41 can add a small-fixture build smoke. |
| Provider smoke tests skip in CI when the optional FEMIC/FreshForge provider set is absent. | The instance CI does not install the provider set. | P41 pins and installs it for CI. |
| The evidence files live under ignored `runtime/`. | They are run artifacts, not source. | The report and docs name the path; P41 can publish a CI artifact. |

## 6. Next phase

Goal: make the smoke automatic.

Tasks:

- P41.1 Install the pinned FEMIC/FreshForge provider set in instance CI.
- P41.2 Run the dry-run/real smoke on a small fixture and upload evidence.
- P41.3 Add a small-fixture build node to the smoke.

Recommended defaults:

- Keep the full inventory out of CI.
- The fixture build is the only model-producing node in CI.
- Upload the evidence JSON as an artifact.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
