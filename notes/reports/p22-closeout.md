# Phase close-out report: P22 Map operations

Phase: P22, Map operations
Parent issue: #198
Pull request: not opened yet
Evidence head: `57a98dd`
Report commit: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-24
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge the P22 pull request, and delete the branch `feature/p22-map-ops`.
2. Close parent issue #198 with a closeout comment that cites the merge commit.
3. Launch P23, Search portfolio and multi-objective: Pareto/archive mode, the tuners, and LP dual
   sensitivity.

Settings changes: none. This phase changes no repository setting, tag, release, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A pre-warm run writes durable tiles and reports hits, misses, bytes, and time. | `scripts/prewarm_tiles.py` opens the app in-process and walks the selected zooms, layers, periods, and runs. Tests: parsing, bounds, periods, a durable-cache write, an unknown layer, and the CLI report. | Met |
| The path-prefix check serves `/prefix/`, static assets, the API, and a tile. | `scripts/check_map_proxy.py` mounts the service at `/ws4` and checks the shell, CSS, JS, summary, viewport map, and MVT tile, plus relative URLs. Tests: clean prefix, invalid prefixes, CLI report. | Met |
| The 1M-fragment benchmark reports peak RSS and enforces the budget. | `scripts/benchmark_map_scale.py` reports `peak_rss_mb` and fails above 4096 MiB. The 1M run measured 130 KB z0, 2.8 KB z12, 25.19 s cold, 0.018 s warm, 1,734.6 MiB peak. | Met |
| `python scripts/dashboard.py` is green. | Lint, format, types, tests, validator, docs, and docstrings pass at `57a98dd`. | Met |

## 2. Workflow compliance

- Parent issue before the branch: #198 was created before `feature/p22-map-ops`.
- Branch from `main`: the branch starts at `e45b189`, which includes P21 and the P20.6 geometry fixes.
- Commit messages start with task IDs: `P22.1`, `P22.2`, `P22.3`.
- Gates for each commit: the dashboard is green at the evidence head.
- Roadmap and changelog in step: P22.1 to P22.3 are checked; the changelog records each.
- Child issues closed with closeout evidence: #199, #200, and #201.
- Approval gates: the phase opened no pull request until this report; it did not merge, tag, release,
  or change a setting.

## 3. Gate evidence

| Gate | Result at `57a98dd` |
| --- | --- |
| lint | green |
| format | green |
| types | green |
| tests | green |
| validator | green |
| docs | green |
| docstrings | green |

## 4. CI evidence

The pull request is opened with this report. Its first CI run is posted on the pull request.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The 1M-fragment gate found a 27 MB zoom-0 tile. | The bare block MVT layer did not apply the low-zoom sampling that the GeoJSON overview path uses; it encoded every point. | Added `_sample_low_zoom`, which samples to at most 5,000 block features below zoom 6. The z0 tile returned to 130 KB; a web test covers the helper. |
| The path-prefix check mounts the app rather than running a live reverse proxy. | A mount is the portable, offline check; a live proxy needs a second process and host setup. | The check covers the shell, static assets, API, and tile through the prefix and asserts relative URLs. A live proxy check remains a deployment step. |

## 6. Next phase

Goal: make the search's quality visible across objectives and tuned configurations.

Tasks:

- P23.1 Add a Pareto/archive mode over target weights or objectives.
- P23.2 Wire the random/grid/Bayesian tuners into a repeatable tuning command.
- P23.3 Add LP dual/reduced-cost sensitivity for the linear target subset.

Recommended defaults:

- Keep the current goal-programming objective; the Pareto archive is an added view, not a replacement.
- Keep the tuners opt-in; a tuned configuration is recorded with its dataset and budget.
- Treat LP duals as advisory, like the P21 sensitivity report.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
