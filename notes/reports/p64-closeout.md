# Phase close-out report: P64 Patchworks-style target charts

Phase: P64, Patchworks-style target charts
Parent issue: #456
Pull request: #461
Status: merged and closed on 2026-10-26 as `8b0d0e6`.
Date: 2026-10-26

## Recommendation

1. Squash-merge the P64 pull request and delete `feature/p64-target-charts`.
2. Close tasks #457/#458/#459 and parent #456.
3. Keep direct chart editing and map palette work for later UI increments.

Settings changes: none.

## Acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Any target account can be pinned and charted. | Plan table watch checkboxes open one chart per account; c5 shows 2 charts, TSA 46 shows 2 accounts. | Met |
| All periods visible with min/max/achieved. | c5: 5 periods; TSA 46: 10 periods with 21 bounded period bands. | Met |
| Exact values and status on hover/table. | Hover readout gives period, min, max, achieved, status; expandable table lists every period. | Met |
| Inactive targets chart as indicators. | Temporary inactive target file: 2 charts, 2 `.inactive` cards, foot says `inactive indicator`. | Met |
| Live solver convergence updates the chart. | 400-iteration c5 run: achieved 1,260.74 → 26,077.22 → 35,150.61 in-place; below → met. | Met |
| iPad/desktop readable. | 1024×768: body 1024, chart grid 655, 2 cards; 1500×1000: 5 periods, 2 cards; no page overflow. | Met |
| Dashboard green. | Green at the report commit. | Met |

## What changed

- `GET /api/runs/{run}/target-series` returns every target account's per-period bounds,
  activation, and target indices, including inactive and multi-period targets.
- Plan opens a large chart canvas instead of the map.
- Pinned target accounts render Patchworks-style period charts:
  - red minimum zone;
  - blue maximum zone;
  - grey acceptable band;
  - black achieved line with status-coloured points;
  - exact hover/selected-period readout;
  - expandable all-period value table.
- Clicking a period selects it in the shell.
- Charts update from the same SSE target snapshots as the live map.
- The chart canvas uses the existing target table as its editor; no solver or target schema
  changes.

## Evidence

Browser smoke `scripts/check_target_charts.py`:

- c5: 2 charts, 2 zones, 2 lines, hover readout, period click 0→1, exit 0.
- TSA 46: 2 charts, 21 zones, 2 lines, period click 1→0, exit 0.

Live convergence (c5, 400 iterations, 20 years): the chart's product target readout moved
from `1,260.74 · below` to `26,077.22 · met`, then `35,150.61 · met` while the solver was
running. No page reload.

## Deviations and limits

- **No drag-to-edit in the chart.** The target table remains the editor; the chart is the
  analyst's readout. Dragging bounds can be a later increment.
- **Flow targets** use the account's period values in the same chart; the table/readout is
  explicit about the target status. A dedicated flow-window visualization is deferred.
- **Bounded periods only:** periods without a configured target row still show the achieved
  line but no red/blue zones; the all-period table marks them `indicator`.
- **No phone support.** The supported small surface remains iPad Pro landscape, per P63.
