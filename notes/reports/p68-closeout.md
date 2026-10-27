# Phase close-out report: P68 Map visual hierarchy

Phase: P68, Map visual hierarchy
Parent issue: #486
Pull request: #491, `feature/p68-map-hierarchy` into `main`
Evidence head: `dcb83ee`, the head that CI run `40465804758` and the local dashboard cover
Report commit: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-27
Status: merged and closed on 2026-10-27 as `694232d`.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #491, and delete the branch `feature/p68-map-hierarchy`.
2. Close task issues #487, #488, and #489, then parent issue #486, with a closeout comment that
   cites the merge commit.
3. Deploy `v76` to the live services.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Untreated blocks read as context and treated blocks are the accent. | c5 `run-dated3`: pale neutral untreated fill with 1,171 red treated blocks; TSA 46 `baseline`: 2,427 treated and 167,127 untreated. | Met |
| The on-map legend updates with the layer and counts. | Browser smoke checks the title, both swatches, both counts, and the base-colour variant (`Base: Compartment`). | Met |
| A selected block has a visible outline in SVG and MapLibre. | c5 MapLibre selection block 5522; SVG fallback selection block 3344. Both render a dark outline. | Met |
| Treated-only is one click and reversible. | Browser smoke toggles untreated off and back on; checkbox, button text, and legend all follow. | Met |
| Unavailable layers are compact, not active controls. | `Unavailable layers` is a closed disclosure with explanatory text and no inputs. | Met |
| Desktop and iPad landscape remain usable. | Browser smoke checks 1024x768, 1194x834, and 1500x1000 with no horizontal overflow. | Met |
| Target charts are unchanged. | `scripts/check_target_charts.py` on c5 `run-base`: 2 charts, 13 zones, centers 0->P1, 1->P2, 20->P21. | Met |
| `python scripts/dashboard.py` is green. | All seven gates green at `dcb83ee`; CI run `40465804758` success. | Met |

Patch, compartment, comparison, and LiDAR legend variants preserve their previous layer logic and
were code-reviewed, but the c5 and TSA 46 datasets do not expose those layers, so they were not
exercised end-to-end. This is a stated coverage limit, not a data change.

## 2. Workflow compliance

- Parent issue before the branch: #486 created before `feature/p68-map-hierarchy`.
- Branch from `main`: forked from `e8b0e8b` (P54.2).
- Commit messages: all start with P68 task IDs.
- Approval gates: the user approved starting P68; merge approval remains outstanding.
- Child issues: #487, #488, and #489 are linked as sub-issues and are closed after merge.

## 3. Gate evidence

`python scripts/dashboard.py` at `dcb83ee`:

| Gate | Result | Seconds |
| --- | --- | --- |
| lint | GREEN | 0.07 |
| format | GREEN | 0.06 |
| types | GREEN | 0.61 |
| tests | GREEN | 132.27 |
| validator | GREEN | 0.79 |
| docs | GREEN | 3.36 |
| docstrings | GREEN | 2.95 |

Overall: GREEN.

`scripts/check_map_hierarchy.py`:

- c5 `run-dated3`: neutral untreated swatch `rgb(217, 228, 220)`, selected block 5522,
  treated-only and restore, Plan hides the legend, responsive widths pass.
- TSA 46 `baseline`: same checks with 2,427 treated and 167,127 untreated.

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 40465804758 | `dcb83ee` | success | Quality gates, clean-checkout contract, dashboard summary, notebook outputs, and pre-commit parity all green. |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| First CI run failed lint/format/types on the new browser smoke. | Long assertions and an untyped Playwright handle. | Fixed in `dcb83ee`; local dashboard and the re-run are green. |
| Patch, compartment, compare, and LiDAR legend variants were not exercised on c5 or TSA 46. | Those datasets do not expose the layers. | Existing styling paths are preserved; the limit is recorded here. |

## 6. Next phase

P69 covers LiDAR/carbon display polish: a coverage badge and dataset-wide scale, a
colour-blind-safe palette, a persistent legend with units, carbon axes/units/tooltips, and compact
empty states. P68 deliberately leaves the target charts and data semantics unchanged.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
