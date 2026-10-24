# Phase close-out report: P20 Production map serving

Phase: P20, Production map serving
Parent issue: #183
Pull request: #185, `feature/p20-map-lod` into `main` (merged)
Evidence head: `ed9693e`, the P20.6 correction. The P20.1-P20.5 head `2123252` is merged.
Date: 2026-10-24
Status: complete. P20.1-P20.5 merged; P20.6 is a post-merge correction on `main`.

## Recommendation

No merge remains. Pull request #185 is merged, and parent issue #183 can close with a closeout
comment that cites `2123252` and the P20.6 correction `ed9693e`.

The next phase is P21, Search quality and validation: search reversion, a multi-seed/engine
validation harness, and a target sensitivity report. Map operations move to P22.

Settings changes: none. This phase changes no repository setting, tag, release, or external
account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A zoom-6 map tile is a block mosaic, not a point or grid substitute. | The TSA 46 z6 overview tile carries 65,268 block polygons in 2.49 MB; the browser screenshot shows the block mosaic over the basemap. | Met |
| A zoom-12 tile carries full block polygons, not a pre-simplified stand-in. | 4.98 KB, 74 block polygons, from `fragments_full.geojson`. | Met |
| The front-end reloads on `moveend` without a request loop. | The shell reloads only after a user drag/zoom; Playwright shows no loop or console errors. | Met |
| The TSA 46 initial viewport stays under 20 MB. | Six z6 overview tiles, largest 2.49 MB; about 15 MB total. | Met |
| Low-zoom tiles use a coarse overview and detail zooms use full geometry. | `--geometry` is `fragments_full.geojson`; `--geometry-overview` is the 100 m layer; z<8 uses the overview, z>=8 uses the full layer. | Met |
| The vector source uses the current run, layer, year, and period. | TSA 46 shell makes 6 z6 MVT requests; TSA 47 makes 4 z7 requests; zooming TSA 46 to z12 fetches 9 z12 tiles with `loaded: true`. | Met |
| Full-run counts come from the map, not the viewport tile. | TSA 46 shows 331 treated / 171,494 untreated; TSA 47 shows 456 / 73,714. | Met |
| The GeoJSON path remains for patches, compartments, and comparison. | `loadMap` calls `hideVectorLayers` for those modes; the P20.1 viewport path stays. | Met |
| A fresh app serves a written tile from disk and reports `disk`. | TSA 46 restarted: first `miss`, second `memory`, after restart `disk`; the file persists under `runtime/tsa46_full/tile-cache/`. | Met |
| The 1,000,000-fragment check passes its size and time thresholds. | 1,000,000 features: z0 129,808 bytes / 29.3 s cold / 0.018 s warm; z12 2,848 bytes / 0.038 s. | Met |
| `python scripts/dashboard.py` is green. | Dashboard job 120780368584 passed on `d40f6b3`. | Met |

## 2. Workflow compliance

- Parent issue before the branch: #183 was created before `feature/p20-map-lod`.
- Branch from `main`: `feature/p20-map-lod` starts at `555e3d5`.
- Commit messages start with task IDs: `P20.1`, `P20.2`, `P20.3`, `P20.4`, `P20.5`.
- Gates for each commit: quality, dashboard, pre-commit, and clean-checkout pass on the evidence
  head; the notebook check was still running.
- Roadmap and changelog in step: the P20 section, tracker, and changelog record each task.
- Child issues closed with closeout evidence: #184, #186, #187, #188, and #189.
- Approval gates: the phase opened the pull request and wrote this report; it did not merge, tag,
  release, or change a setting.

## 3. Gate evidence

| Gate | Result at `d40f6b3` |
| --- | --- |
| lint | green |
| format | green |
| types | green |
| tests | green (53 web/scale tests plus the full suite) |
| validator | green |
| docs | green |

## 4. CI evidence

| Run ID | Head | Conclusion | Notes |
| --- | --- | --- | --- |
| 40063018637 | `d40f6b3` | Quality, dashboard, pre-commit, clean-checkout pass | Notebook output still running |
| Posted on PR #185 | Report commit | See the PR comment | The run for this report |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The first P20.2 vector-source attempt did not request tiles. | Installing the source during the initial style load left the MapLibre worker idle. | Restored the verified viewport shell, deferred the source to P20.3, installed it after `idle`, and added the browser smoke. |
| The P20.3 CI run failed the docstring audit for `check_map_browser.main`. | The CLI docstring had no Parameters/Returns sections. | Added them; the quality, dashboard, and pre-commit jobs pass. |
| The P20.4 branch added `--tile-cache` as a `create_app` parameter named like the in-memory dict. | Name collision. | Renamed the parameter `tile_cache_dir`; the CLI flag stays `--tile-cache`. |
| The first LOD returned treated centroids, then a grid. Both were rejected as not a block map. | The implementation optimized payload size before matching the established exact-geometry decision. | P20.6 restored full geometry at detail zooms and a 100 m overview below zoom 8; the centroid and grid MVT paths are removed. |
| P20.6 landed directly on `main` after #185 had merged. | The branch was already merged and the correction was committed from the shared checkout. | Disclosed here and in the changelog; the correction is on `main` and the P20.6 issue records it. |

## 6. Next phase

Goal: make the search's quality measurable and improve it with the smallest, highest-value changes.

Tasks:

- P21.1 Add search reversion to SA, tabu, and ILS.
- P21.2 Add `ws4 validate-search`, a multi-seed, multi-engine validation harness.
- P21.3 Add a target sensitivity report from the MIP/LP: slack, binding status, and marginal relaxation value.
- P21.4 Add a threshold-accepting engine.

Recommended defaults:

- Reversion resets the current solution to the best every 10-50 accepted moves, configurable and
  recorded in telemetry.
- Validation uses the existing engines, seeds, and budgets, and reports best/mean/median/worst,
  standard deviation, feasibility rate, and the MIP gap when enabled.
- Sensitivity is advisory and does not change a run.
- Map operations move to P22.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
