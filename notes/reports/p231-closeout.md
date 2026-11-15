# P231 close-out: age-based volume curves

Date: 2026-11-15
Phase: P231 (#1326)
Branch: `feature/p231-age-curves`
Tasks: P231.1 (#1327), P231.2 (#1328), P231.3 (#1329)
Design note: `notes/design/ws4-age-volume-curves.md`
Report: `notes/reports/p231-age-curves.md`

## Result

The process bridge can now use the same age-based yield curve as the estate fixture. The shared
CC schedule still reports **340 m3** on both sides.

## What changed

- `VolumeBridgeConfig.age_volume_curves`.
- Interpolation, endpoint clamping, validation, and serialization.
- Shared-schedule test switched to the natural curve.
- Documentation and report.

## Evidence

- Bridge tests: 8 passed.
- Shared-schedule test: 1 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Curve `PL`: 0->0, 40->120, 60->170.
- Estate and process final volume: **340 m3**; difference 0.

## Boundary

Test curves, not a compiled management yield table. No fire, succession, or regeneration. Not an
observed-data validation.

## Next

Load the compiled estate yield curves into the bridge instead of the test curve.

## Pull request

PR: #TBD is queued for maintainer approval. Do not merge without approval.
