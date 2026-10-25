# Phase close-out report: P48 Ground-plot volume and DBH validation

Phase: P48, Ground-plot volume and DBH validation
Parent issue: #324
Pull request: this docs/tracker PR
Companion pull requests: femic-tsa46-instance #32, femic-tsa47-instance #33
Date: 2026-10-25
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge this docs/tracker pull request.
2. Close parent issue #324 with a closeout comment that cites the companion merges.
3. Launch P49, Managed/young plot acquisition and validation pre-registration: find an
   independent remeasured sample large enough to test the Cw/Hw 16-80 gap, or close the question
   as data-limited.

Settings changes: none. This phase changes no repository setting, tag, release, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Both instances trace the plot source, matching rules, and sample sizes. | `docs/ground-plot-validation.rst`; sample-frame tables and non-match counts. | Met |
| Volume, DBH, height, and stems are reported by species and age class where n permits. | Per-species, per-age, and species-by-age tables; full stratified CSV. | Met |
| The decision is explicit: retain production curves or adopt a justified alternative. | ADR 0002 in both instances retains the production curves. | Met |
| No curve or AAC change occurs without a separate ADR. | No profile, curve, target, or schedule changed. | Met |
| Both instance dashboards and the ws4 docs build are green. | Instance CI and dashboard green; this PR builds docs with warnings as errors. | Met |

## 2. Workflow compliance

- Parent issue #324 and children #325–#327 were created before the branches.
- Instance branches: `feature/p48-ground-plots`.
- Companion PRs: femic-tsa46-instance #32, femic-tsa47-instance #33.
- Commit messages start with `P48`.

## 3. Merge evidence

- femic-tsa46-instance #32: `8a7f0f1`.
- femic-tsa47-instance #33: `2fe48cc`.

## 4. Behaviour

- Each instance adds a ground-plot validation page linked from the index, benchmark, decisions,
  limitations, sidecar, and validation notes.
- `scripts/summarize_ground_plot_validation.py` writes a long-form stratified table from the
  tracked observations. Tests cover the grouping, small-sample handling, and CLI.
- TSA 46: 20 matched rows from 17 sites (8 CMI, 6 NFI, 6 YSM). Aggregate volume bias -71.1
  m3/ha (-32.8%), DBH -11.2 cm (-51.6%), height -2.1 m (-12.9%), stems +44.7 sph (+6.8%).
  Most cells have n=1-5 and the CMI rows are old.
- TSA 47: 506 matched rows from 130 sites (480 VRI, 11 YSM, 8 NFI, 7 CMI). Aggregate volume
  bias -49.6 m3/ha (-10.0%), DBH -4.3 cm (-13.6%), height -1.2 m (-4.6%), stems -110.8 sph
  (-14.7%). The 26-row managed/young subset is more negative on volume (-27.7%) and stems
  (-30.1%). Cw and Hw carry most of the gap; Ba and Fd are near neutral.
- ADR 0002 retains the production TSR-consistent BatchTIPSY curves in both instances. No volume,
  DBH, height, stems, or AAC change.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The sample is not random and VRI dominates TSA 47. | Public plot availability and matching filters. | Report VRI and managed/young separately; do not fit a global multiplier. |
| TSA 46 cannot quantify accuracy. | 20 rows, 17 sites, old CMI component. | Record the data limit; prioritize more managed/young Cw and Hw plots. |
| The lane does not persist per-plot exclusion reasons. | Existing matching script keeps only matched rows. | Report unmatched counts and name the filters; add reason codes in a future data-acquisition phase if needed. |
| The summary script is duplicated in the two independent instances. | The instances deliberately do not import each other. | Keep the copies aligned; the tests and output schema are the contract. |

## 6. Next phase

Goal: acquire or bound an independent managed/young validation sample.

Tasks:

- P49.1 Inventory remeasured CMI/PSP plots inside each TSA with management-origin metadata.
- P49.2 Pre-register the minimum sample and stratification before fitting any correction.
- P49.3 Run the test if the sample is sufficient; otherwise close the question as data-limited.

Recommended defaults:

- Keep the production curves unless the sample supports a species-by-age effect.
- Do not tune to the AAC.
- Do not use VRI audits as a substitute for remeasured managed plots.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
