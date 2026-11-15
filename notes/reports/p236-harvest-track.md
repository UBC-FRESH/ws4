# P236 report: five-year harvest and track change

Date: 2026-11-15
Phase: P236 (#1344)
Branch: `feature/p236-harvest-track`
Design note: `notes/design/ws4-harvest-track.md`

## Result

A timed CC inside a five-year run exposes the missing track-change state in the process bridge.

## Evidence

| Case | Estate | Process | Difference |
| --- | --- | --- | --- |
| four transitions | 390 | 360 | -30 (-7.69%) |
| five transitions | 390 | 365 | -25 (-6.41%) |

- Estate fragment 1 uses managed curve 3 at age 2: 3 × 10 = 30.
- Process uses natural curve 2 for all cohorts and keeps the bare cohort at age 0.
- The five-transition case also carries the P235 one-step offset.
- Test: 1 passed.
- Full dashboard: **OVERALL: GREEN**.

## Boundary

No track state in the process bridge; single species; no fire/regeneration. Diagnostic only.

## Next

Add track/curve identity to process cohorts or the bridge, then re-run this case.
