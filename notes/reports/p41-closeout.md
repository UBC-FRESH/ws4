# Phase close-out report: P41 Provider smoke in CI

Phase: P41, Provider smoke in CI
Parent issue: #303
Pull request: this docs/tracker PR
Companion pull requests: femic-tsa46-instance #30, femic-tsa47-instance #31
Date: 2026-10-25
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge this docs/tracker pull request.
2. Close parent issue #303 with a closeout comment that cites the companion merges.
3. Launch P42, Model limitations and decision record: publish the runbook-level limitations and
   link them from the instance sites.

Settings changes: none. This phase changes no repository setting, tag, release, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| The CI smoke includes build_dataset, validate, provenance, schedule, and simulate. | `tsaXX_ws4_ci_smoke.yaml` in both instances. | Met |
| Every node succeeds on the tiny fixture. | Both `Provider smoke` jobs pass all five nodes. | Met |
| The evidence JSON is uploaded as a CI artifact. | `provider-smoke-evidence` upload step in both workflows. | Met |
| The normal quality gates remain green. | Quality gates, dashboard, and pre-commit parity pass in both instances. | Met |

## 2. Workflow compliance

- Parent issue #303 and children #304–#306 were created before the branches.
- Instance branches: `feature/p41-ci-smoke`.
- Companion PRs: femic-tsa46-instance #30, femic-tsa47-instance #31.
- Commit messages start with `P41`.

## 3. Merge evidence

- femic-tsa46-instance #30: `89f134d`.
- femic-tsa47-instance #31: `e25530b`.

## 4. Behaviour

- The CI job installs `requirements-freshforge.txt`, pinned to the FEMIC P37.2 commit and the ws4
  P40 commit.
- It runs `scripts/run_provider_smoke.py` on `tests/fixtures/provider_smoke`.
- The graph builds a tiny matrix, validates it, applies the provenance sidecar, builds a baseline
  schedule, and simulates one year.
- `runtime/smoke/ci-evidence.json` is uploaded as `provider-smoke-evidence`.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The CI fixture is synthetic, not the full TSA. | A full inventory build is too large for CI. | The full matrices remain covered by the local P40 smoke and the instance build runbooks. |
| The provider requirements use git pins. | The packages are not released together. | The pins name exact commits; update them when the provider contract changes. |

## 6. Next phase

Goal: make the model's limitations a first-class decision record.

Tasks:

- P42.1 Publish the instance-level limitations page (VDYP transform, predecessor THLB, AAC ceiling).
- P42.2 Link it from the instance index, model-build page, and provenance report.
- P42.3 Add a short decision record for the accepted model boundary.

Recommended defaults:

- Keep the page qualitative and cite the source notes.
- Do not present the AAC as an operational guarantee.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
