# Phase close-out report: P44 Comparison and map operations

Phase: P44, Comparison and map operations
Parent issue: #341
Pull request: this P44 PR
Status: merged and closed on 2026-10-25 as `05c3b44`.
Date: 2026-10-25

## Recommendation

1. Squash-merge the P44 pull request and delete `feature/p44-compare-ops`.
2. Close tasks #342/#343/#344 and parent #341.

Settings changes: none.

## Acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A repeated compare tile hits disk. | Endpoint test creates a second app over the same cache; header is `disk`. | Met |
| Pre-warm covers compare tiles. | `prewarm_tiles.py --layers compare --compare-against run2` writes the pair tile. | Met |
| Browser check verifies tiles/counts/details. | `check_compare_browser.py` on TSA 46: 6 compare tiles, A only 2,427, B only 507, Kind column. | Met |
| Cold/warm gate. | c5 six z9 tiles: 2.063 s cold first, 13.336 s cold total, 0.003 s warm first, 0.018 s warm; budgets 120/10 s. | Met |
| Dashboard green. | Green at the report commit. | Met |

## Deviations

- The browser smoke checks map tiles, counts, and the Kind column; block-level detail is covered by
  the compare-tile property test rather than a synthetic map click.
- The benchmark is opt-in and not a CI gate; the c5 result is recorded here.
- The compare cache is per run pair; changing the pair warms new tiles.
