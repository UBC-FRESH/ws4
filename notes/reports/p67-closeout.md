# Phase close-out report: P67 Target chart period hit zones

Phase: P67, Target chart period hit zones
Parent issue: #479
Pull request: #482
Status: queued for approval. Not merged.
Date: 2026-10-26

## Recommendation

1. Squash-merge the P67 pull request and delete `feature/p67-target-hit-zone`.
2. Close task #480 and parent #479.
3. Deploy `v75`.

## Acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Period-center clicks select the matching period. | c5 `run-base`: centers 0→P1, 1→P2, 20→P21. | Met |
| Right-side workaround removed. | Pointer selection uses the period hit element; edge clicks select the column they land in. | Met |
| Selected period highlighted. | `.target-chart-selected-period` present in browser smoke. | Met |
| Drag remains on the selected period. | Drag handler uses the hit element's period index. | Met |
| Dashboard green. | Green at the report commit. | Met |

## What changed

- Every chart hit column now carries its period index.
- Pointer-down resolves the period from that hit element, with coordinate math only as a
  fallback outside the plot.
- The selected period is drawn as a light highlight behind the zones.
- The chart smoke now clicks P1, P2, and the last period centers and asserts the selected period.

## Limits

- The fix is pointer-based; keyboard period selection still goes through the shell controls.
- No data or target semantics changed.
