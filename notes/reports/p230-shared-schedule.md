# P230 report: shared-schedule process/estate comparison

Date: 2026-11-15
Phase: P230 (#1313)
Branch: `feature/p230-shared-schedule`
Design note: `notes/design/ws4-shared-schedule.md`

## Result

The same CC schedule now runs through both the estate simulator and the process engine and reports
the same final volume.

## Evidence

- Test: 1 passed in `tests/test_process_estate_shared_schedule.py`.
- Estate final `feature.Volume`: **340**.
- Process final `bridge.volume_m3`: **340**.
- Comparison absolute difference: **0**.
- Comparison artifact written.
- Full dashboard: **OVERALL: GREEN**.

## Boundary

Synthetic fixture and provisional linear volume bridge. No fire, succession, regeneration, or real
yield curves in this comparison. Not an observed-data validation.

## Next

Replace the linear bridge with real yield curves and run the comparison on a compiled estate
dataset with an ecosystem package.
