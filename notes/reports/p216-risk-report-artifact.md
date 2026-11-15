# P216 report: process fire-risk report artifact

Date: 2026-11-15
Phase: P216 (#1259)
Branch: `feature/p216-risk-report-artifact`
Design note: `notes/design/ws4-process-risk-artifact.md`

## Result

`ProcessFireRiskReport.write` now emits a stable artifact directory with account values,
aggregated risk rows, and a JSON summary.

## Evidence

- Tests: 8 passed in `tests/test_process_fire_risk.py`.
- Two-scenario report: schema, scenario ids, target account, objective verified.
- Both CSVs and the JSON file written.
- Empty report rejected.
- Full dashboard: **OVERALL: GREEN**.

## Boundary

Final-period report only. No optimizer search integration, calibration, or observed-perimeter
validation.

## Next

Use the report artifact in the optimizer's risk verification path for a process scenario set.
