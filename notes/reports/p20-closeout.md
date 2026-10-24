# Phase close-out report: P20 Production map serving

Phase: P20, Production map serving
Parent issue: #183
Pull request: #185, `feature/p20-map-lod` into `main`
Evidence head: `d40f6b3`. CI run 40063018637 is green in quality, dashboard, pre-commit, and
clean-checkout; the notebook-output job was still running when this report was written.
Report commit: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-24
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #185, and delete the branch `feature/p20-map-lod`.
2. Close parent issue #183 with a closeout comment that cites the merge commit.
3. Launch P21, Map operations: pre-warm the durable cache, record a reverse-proxy deployment
   check, and add a memory profile for the 1M-fragment cold build.

Settings changes: none. This phase changes no repository setting, tag, release, or external
account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A map request at zoom 6 with the full TSA bbox returns centroids, not polygons. | TSA 46 zoom-5 request returns 331 treated centroids in 66 KB; the map response reports `overview: true`. | Met |
| A map request at zoom 12 with a small bbox returns only intersecting blocks. | TSA 46 zoom-12 viewport is 524 KB; the tile path returns 3.1 KB for 74 intersecting blocks. | Met |
| The front-end reloads on `moveend` without a request loop. | The shell reloads only after a user drag/zoom; Playwright shows one initial map request and no loop or console errors. | Met |
| The TSA 46 initial map payload is below 20 MB. | 66 KB at zoom 5. | Met |
| A zoom-0 MVT tile is under 20 KB and carries treated centroids. | 8.5 KB, 331 treated features. | Met |
| A zoom-12 MVT tile is under 1 MB and carries only intersecting polygons. | 3.1 KB, 74 features, 57 ms warm. | Met |
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

## 6. Next phase

Goal: keep the map operationally fast and deployable on a shared host.

Tasks:

- P21.1 Pre-warm the durable tile cache for a model tree.
- P21.2 Record a reverse-proxy deployment check under a path prefix.
- P21.3 Add a memory profile for the 1M-fragment cold build and decide the cache/index budget.

Recommended defaults:

- Keep the current LOD policy: treated centroids below zoom 10, polygons at 10+.
- Keep the durable cache opt-in via `--tile-cache`.
- Treat the 29.3 s cold build as a pre-warm step, not a user-facing request.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
