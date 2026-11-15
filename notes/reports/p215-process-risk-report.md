# P215 report: process fire-risk evaluation report

Date: 2026-11-14
Phase: P215 (#1253)
Branch: `feature/p215-process-risk-report`
Design note: `notes/design/ws4-process-risk-report.md`

## Result

Process fire-regime summaries can now be evaluated against risk-aggregated targets with the
existing objective code.

## Evidence

- Tests: 6 passed in `tests/test_process_fire_risk.py`.
- Zero-minimum mean target: objective 0.
- Minimum raised by 2 above the aggregate: objective 2.
- Report summary: schema `ws4.process-fire-risk-accounts.v1`, both scenarios, objective.
- Full dashboard: **OVERALL: GREEN**.

## Boundary

No optimizer search change, calibration, or observed-perimeter validation. Final-period only.

## Next

Wire the report into the optimizer's risk verification path for a process scenario set.
