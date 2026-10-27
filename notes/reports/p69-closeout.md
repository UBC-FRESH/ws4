# Phase close-out report: P69 LiDAR and carbon display polish

Phase: P69, LiDAR and carbon display polish
Parent issue: #494
Pull request: #500, `feature/p69-lidar-carbon-polish` into `main`
Evidence head: `8c42173`, the head that CI run `40479144595` covers
Report commit: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-27
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #500, and delete `feature/p69-lidar-carbon-polish`.
2. Close task issues #495, #496, and #497, then parent issue #494, with a closeout comment
   that cites the merge commit.
3. Deploy `v77` to the live services.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| LiDAR coverage is dataset-wide, not viewport-derived. | `/api/lidar` on the FEMIC GNN instance: `total_blocks` 26,801; CHM mean `valid_count` 184; badge `184 / 26,801 blocks · 0.7%`. | Met |
| The selected field shows valid blocks, percentage, unit, and dataset-wide range. | CHM mean: 184 valid, 0.7%, unit m, range 1.06–26.18 m. | Met |
| The palette is colour-blind-safe and missing values are neutral. | Viridis stops `#440154` → `#fde725`; computed gradient and neutral `#d5dce5` swatch verified. | Met |
| Panel and map legend agree. | Both show CHM mean, 1.06–26.18 m, 184 / 26,801, and **No value**. | Met |
| Carbon accounts use human labels and units. | TSA 46 GCBM run: 12 accounts; options use labels such as **Ecosystem carbon (tC)** and **Net ecosystem CO₂e flux (tCO2e/yr)**. | Met |
| The carbon chart has labelled axes and a working hover/tap readout. | 21 points, compact year/value ticks, Year 0/10/20 labels, tooltip **Year 10 · 2,084,414.05 tC**; latest readout **2.09M tC** at year 20. | Met |
| Empty states are compact and leave no empty chart frame. | c5: LiDAR and Carbon tabs stay visible with one-line empty states; chart, content, and legend are hidden. | Met |
| Desktop and iPad landscape remain usable. | Both browser checks assert no horizontal overflow at 1024×768; 1194/1500 were checked during P68 map work. | Met |
| No map or target-chart regression. | Map hierarchy smoke and target-chart smoke both pass on the P69 c5 service. | Met |
| `python scripts/dashboard.py` is green. | All seven gates green at `8c42173`; CI run `40479144595` success. | Met |

## 2. Workflow compliance

- Parent issue before the branch: #494 created before `feature/p69-lidar-carbon-polish`.
- Branch from `main`: forked from `2b866eb` (P68 status).
- Commit messages: both implementation commits start with P69 task IDs.
- Child issues: #495, #496, and #497 are linked as sub-issues and are closed after merge.
- Approval gates: the user approved starting P69; merge approval remains outstanding.

## 3. Gate evidence

`python scripts/dashboard.py` at `8c42173`:

| Gate | Result | Seconds |
| --- | --- | --- |
| lint | GREEN | 0.08 |
| format | GREEN | 0.07 |
| types | GREEN | 0.77 |
| tests | GREEN | 124.69 |
| validator | GREEN | 0.77 |
| docs | GREEN | 3.05 |
| docstrings | GREEN | 2.58 |

Overall: GREEN. Total coverage 90.23%; the new browser functions are marked as browser-only.

`scripts/check_data_panels.py`:

- LiDAR service: coverage badge, dataset range, viridis gradient, missing swatch, map legend.
- Carbon service: human account labels, units, axes, 21 points, tooltip.
- c5 empty service: both tabs visible with compact empty states and no chart chrome.

Additional regression checks: `check_map_hierarchy.py` and `check_target_charts.py` both pass.

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 40479144595 | `8c42173` | success | Quality gates, dashboard summary, notebook outputs, clean-checkout contract, and pre-commit parity all green. |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The FEMIC LiDAR instance has only 184 blocks with CHM means. | Raster zonal coverage is genuinely sparse; valid-pixel fields cover all blocks. | The badge reports 0.7% and the map leaves the other blocks neutral rather than inventing values. |
| TSA 46 has no GCBM comparison rows. | That run has carbon accounts and pools but no `gcbm_compare.csv`. | The comparison block is hidden; no empty table is shown. |
| The first full test run landed at 89.84% coverage. | The new browser script and a pre-existing glob-branch gap. | Browser functions are excluded as browser-only; added focused wildcard tests in `tests/test_check_workflow.py`. Coverage is 90.23% at the evidence head. |

## 6. Next phase

P70 is not yet scoped. The next recommended surface is the target table: compact account labels, units,
sorting, and inline bound status, followed by map data filters. It should not change the target-chart
editing contract shipped in P65–P67.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
