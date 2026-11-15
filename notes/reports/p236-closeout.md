# P236 close-out: five-year harvest and track change

Date: 2026-11-15
Phase: P236 (#1344)
Branch: `feature/p236-harvest-track`
Tasks: P236.1 (#1345), P236.2 (#1346)
Design note: `notes/design/ws4-harvest-track.md`
Report: `notes/reports/p236-harvest-track.md`

## Result

A timed CC inside a five-year run exposes the missing track-change state in the process bridge.

## Evidence

- Estate final: 390 m3.
- Four transitions: 360 m3, difference -30 (-7.69%).
- Five transitions: 365 m3, difference -25 (-6.41%).
- Test: 1 passed; full dashboard **OVERALL: GREEN**.
- The gap is the managed age-2 contribution and the one-step horizon offset.

## Boundary

No track state in the process bridge; single species; no fire/regeneration. Diagnostic only.

## Next

Add track/curve identity to process cohorts or the bridge, then re-run this case.

## Pull request

PR: #TBD is queued for maintainer approval. Do not merge without approval.
