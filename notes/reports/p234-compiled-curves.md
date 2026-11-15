# P234 report: compiled yield curves in the process bridge

Date: 2026-11-15
Phase: P234 (#1335)
Branch: `feature/p234-compiled-curves`
Design note: `notes/design/ws4-compiled-curves.md`

## Result

The process bridge now loads the compiled dataset yield curve and still matches the estate
schedule at 340 m3 after CC.

## Evidence

- Bridge tests: 8 passed.
- Shared-schedule tests: 2 passed.
- Compiled `PL` natural curve: 0->0, 40->120, 80->220.
- Age 60 interpolates to 170.
- Estate and process final volume: **340 m3**; difference 0.
- Full dashboard: **OVERALL: GREEN**.

## Boundary

Single species and one compiled curve. No track-change semantics beyond the harvested age-0 case.
No fire, succession, or regeneration. Not an observed-data validation.

## Next

Use the compiled curve table for multiple species and tracks, then add fire/succession to the
shared schedule.
