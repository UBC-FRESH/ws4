# P235 close-out: five-year succession offset

Date: 2026-11-15
Phase: P235 (#1340)
Branch: `feature/p235-succession-offset`
Tasks: P235.1 (#1341), P235.2 (#1342)
Design note: `notes/design/ws4-succession-offset.md`
Report: `notes/reports/p235-succession-offset.md`

## Result

Four LANDIS transitions match the five-year estate final offset. Five transitions are one annual
step ahead.

## What changed

- Five-year succession comparison test.
- Offset convention documented on the succession page.
- Design note and report.

## Evidence

- Test: 1 passed.
- Four transitions: 750 vs 750, difference 0.
- Five transitions: 762.5 vs 750, difference +12.5 (1.667%).
- Full dashboard: **OVERALL: GREEN**.

## Boundary

No fire, harvest, or regeneration. Single species and one compiled curve. Offset convention only,
not calibration.

## Next

Use four transitions per five estate accounting years, or make the process API accept an explicit
final offset.

## Pull request

PR: #TBD is queued for maintainer approval. Do not merge without approval.
