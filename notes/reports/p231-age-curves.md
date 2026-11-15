# P231 report: age-based volume curves

Date: 2026-11-15
Phase: P231 (#1326)
Branch: `feature/p231-age-curves`
Design note: `notes/design/ws4-age-volume-curves.md`

## Result

The process bridge can now use the same age-based yield curve as the estate fixture. The shared
CC schedule still reports **340 m3** on both sides.

## Evidence

- Bridge tests: 8 passed.
- Shared-schedule test: 1 passed.
- Curve `PL`: 0->0, 40->120, 60->170.
- Estate final `feature.Volume`: 340.
- Process final `bridge.volume_m3`: 340.
- P223 difference: 0.
- Full dashboard: **OVERALL: GREEN**.

## Boundary

Test curves, not a compiled management yield table. No fire, succession, or regeneration. Not an
observed-data validation.

## Next

Load the compiled estate yield curves into the bridge instead of the test curve.
