# P223 report: process/estate account comparison

Date: 2026-11-15
Phase: P223 (#1292)
Branch: `feature/p223-account-comparison`
Design note: `notes/design/ws4-account-comparison.md`

## Result

Mapped process and estate accounts can now be compared at the final period with a stable
JSON/CSV report.

## Evidence

- Tests: 5 passed.
- `bridge.volume_m3=100` vs `feature.Volume=120`: absolute `-20`, relative `-0.1667`.
- Scenario selection and missing-account failures verified.
- Zero estate value omits relative difference.
- Full dashboard: **OVERALL: GREEN**.

## Boundary

One final period and an explicit mapping only. No default mapping, engine runs, calibration, or
observed-perimeter validation.

## Next

Run both sides on a shared schedule and feed their account files into this comparison.
