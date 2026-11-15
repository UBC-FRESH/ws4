# P223 close-out: process/estate account comparison

Date: 2026-11-15
Phase: P223 (#1292)
Branch: `feature/p223-account-comparison`
Tasks: P223.1 (#1293), P223.2 (#1294)
Design note: `notes/design/ws4-account-comparison.md`
Report: `notes/reports/p223-account-comparison.md`

## Result

Mapped process and estate accounts can now be compared at the final period with a stable
JSON/CSV report.

## What changed

- `ws4/opt/account_compare.py`.
- Explicit account mapping and final-period selection.
- Absolute and relative differences; zero estate value omits relative.
- Scenario selection and missing-account validation.
- Five tests and documentation.

## Evidence

- Tests: 5 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Exact case: process 100 vs estate 120 gives absolute -20, relative -0.1667.

## Boundary

One final period and an explicit mapping only. No default mapping, engine runs, calibration, or
observed-perimeter validation.

## Next

Run both sides on a shared schedule and feed their account files into this comparison.

## Pull request

Merged as `15d9ec9` (PR #1298); branch deleted.
