# Phase close-out report: P47 Model boundary record

Phase: P47, Model boundary record
Parent issue: #311
Pull request: this docs/tracker PR
Companion pull requests: femic-tsa46-instance #31, femic-tsa47-instance #32
Date: 2026-10-25
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge this docs/tracker pull request.
2. Close parent issue #311 with a closeout comment that cites the companion merges.
3. Launch P48, Ground-plot volume and DBH validation: close the remaining validation gap named
   by the new ADR, or record a bounded decision that the public data are insufficient.

Settings changes: none. This phase changes no repository setting, tag, release, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Each instance has an accepted ADR naming the predecessor THLB, curve provenance, and AAC limits. | `notes/adr/0001-model-boundary.md` in both instances. | Met |
| Each docs site has a limitations page in the toctree. | `docs/limitations.rst`; index toctree. | Met |
| The model-build and decisions pages link it. | `:doc:` links in both pages. | Met |
| Both instance dashboards are green. | All instance quality gates pass in CI. | Met |

## 2. Workflow compliance

- Parent issue #311 and children #312–#314 were created before the branches.
- Instance branches: `feature/p47-boundary`.
- Companion PRs: femic-tsa46-instance #31, femic-tsa47-instance #32.
- Commit messages start with `P47`.

## 3. Merge evidence

- femic-tsa46-instance #31: `ade9123`.
- femic-tsa47-instance #32: `b65cf8d`.

## 4. Behaviour

- The ADRs accept the full dissolved TSA boundary, the predecessor-derived THLB target, the
  TSR-consistent BatchTIPSY managed curves, and the AAC as a policy ceiling.
- The limitations pages name the inventory, curve, THLB, AAC, scheduling, market, fire, access,
  climate, and Indigenous land-use boundaries. They link the ADR and the upstream ws4 boundary.
- The sidecars now record the production managed-curve lane. The `managed_curve_mode:
  vdyp_transform` profile flag is described as the FEMIC data-preparation lane, not the production
  managed-curve source. The dated VDYP-transform runs remain comparison backups.
- The sidecars carry `limitations_url` and name the deterministic opening-first seed.
- The ws4 GBR provenance reference and limitations guide are updated to match.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The ADR is a project decision, not a professional sign-off. | The project has no regulatory mandate. | The limitations page says so explicitly; a future reviewed netdown or TSR triggers a new ADR. |
| Volume, DBH, and mortality validation remain incomplete. | Public plot data are sparse or audit-grade. | P48 is scoped to close the gap or record insufficient data. |
| The sidecar is corrected in place rather than versioned as a second file. | The sidecar describes the current production matrix, not a historical run. | The dated VDYP-transform runtime remains available for comparison. |

## 6. Next phase

Goal: close or bound the remaining volume and DBH validation gap.

Tasks:

- P48.1 Reconcile the FAIB/Nemora plot set against the production TSR lane for both TSAs.
- P48.2 Report volume, DBH, height, and stems by species and age class with sample sizes.
- P48.3 Decide whether to change the curve lane or record that public data are insufficient.

Recommended defaults:

- Keep the production curves unchanged unless the validation is strong enough to justify a new
  ADR.
- Do not tune to the AAC.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
