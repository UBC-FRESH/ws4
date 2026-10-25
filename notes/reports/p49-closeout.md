# Phase close-out report: P49 Managed/young validation pre-registration

Phase: P49, Managed/young validation pre-registration
Parent issue: #335
Pull request: this docs/tracker PR
Companion pull requests: femic-tsa46-instance #33, femic-tsa47-instance #34
Date: 2026-10-25
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge this docs/tracker pull request.
2. Close parent issue #335 with a closeout comment that cites the companion merges.
3. Launch P50, Runtime provenance and release verification: refresh the sidecars beside the
   existing matrices, re-run the quality gate, and verify that the published limitations match the
   artifacts. The managed/young data acquisition is a parallel external action, not a coding phase.

Settings changes: none. This phase changes no repository setting, tag, release, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| The inventory names candidate counts, fields, and gaps. | `docs/ground-plot-preregistration.rst`; tracked candidate CSV. | Met |
| The plan fixes the target population, exclusions, strata, metrics, and decision rule before results. | Pre-registered four-strata protocol; minimum 30 sites per stratum. | Met |
| The decision is explicit and does not tune to the AAC. | ADR 0003 records data-limited; no curve or AAC change. | Met |
| No curve change occurs unless the pre-registered sample is met. | Zero eligible sites; production lane retained. | Met |
| Both instance dashboards and the ws4 docs build are green. | Instance CI/dashboards green; this PR builds docs with warnings as errors. | Met |

## 2. Workflow compliance

- Parent issue #335 and children #336–#338 were created before the branches.
- Instance branches: `feature/p49-preregistration`.
- Companion PRs: femic-tsa46-instance #33, femic-tsa47-instance #34.
- Commit messages start with `P49`.

## 3. Merge evidence

- femic-tsa46-instance #33: `405aa85`.
- femic-tsa47-instance #34: `48006d1`.

## 4. Behaviour

- Each instance adds a pre-registration page, candidate inventory CSV, inventory script, tests, and
  ADR 0003. The page, decisions page, limitations page, benchmark, P48 validation page, sidecar,
  and validation notes link the result.
- TSA 46 inventory: 205 candidate sites / 460 visits; 117 PSP (98 PSP_G, 19 PSP_R) and 88 non-PSP
  (55 CMI, 14 NFI, 4 VRI, 15 YSM); 125 remeasured sites and 89 young sites.
- TSA 47 inventory: 351 candidate sites / 572 visits; 30 PSP (3 PSP_G, 27 PSP_R) and 321 non-PSP
  (16 CMI, 8 NFI, 281 VRI, 16 YSM); 35 remeasured sites and 161 young sites.
- The public header/visit/tree schema has no management-origin field. The remeasured candidates
  are natural PSP_G, experimental PSP_R, or origin-unknown NFI.
- The pre-registered test requires 30 independent remeasured sites in each of four Cw/Hw 16-50
  and 51-80 strata, all with documented management origin. Zero sites meet it.
- No confirmatory test was run. Production remains on the TSR-consistent BatchTIPSY lane; no
  curve or AAC change.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The phase did not acquire new plot data. | The phase is an inventory and pre-registration, not a data-purchase authority. | Record data acquisition as a parallel external action; do not force a result from existing plots. |
| TSA 47 has no committed raw FAIB download tree. | The public raw data are large and external; the inventory ran against the shared public extraction. | Track the inventory CSV and script; document the public source paths. |
| The 30-per-stratum minimum is a project pre-specification, not a formal power calculation. | No defensible variance estimate exists for the missing managed sample. | State it as a feasibility threshold; revise only in a new pre-registration before data collection. |
| No management-origin field exists. | Public FAIB schema limitation. | Do not treat program code or purpose code M as origin; request managed-origin metadata with the data. |

## 6. Next phase

Goal: make the runtime artifacts match the published provenance after P47–P49.

Tasks:

- P50.1 Refresh `data_quality.yaml` beside the current TSA 46 and TSA 47 matrices.
- P50.2 Re-run `ws4 quality --check` and capture the report.
- P50.3 Verify the published limitations, sidecars, and Pages links against the runtime artifacts.

Recommended defaults:

- Keep the full inventory and `runtime/` artifacts out of Git.
- Do not rebuild the matrix unless the sidecar copy and quality gate fail.
- Do not change curves or the AAC.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
