# P215 close-out: process fire-risk evaluation report

Date: 2026-11-14
Phase: P215 (#1253)
Branch: `feature/p215-process-risk-report`
Tasks: P215.1 (#1254), P215.2 (#1255), P215.3 (#1256)
Design note: `notes/design/ws4-process-risk-report.md`
Report: `notes/reports/p215-process-risk-report.md`

## Result

Process fire-regime summaries now evaluate against risk-aggregated targets with the existing
objective code through `evaluate_process_fire_risk`.

## What changed

- `ProcessFireRiskReport`.
- `evaluate_process_fire_risk`.
- Exact zero and penalty tests on a real process ensemble.
- Reference and design documentation.

## Evidence

- Process fire-risk tests: 6 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Zero-minimum mean target: objective 0.
- Minimum raised by 2 above the aggregate: objective 2.
- Report schema: `ws4.process-fire-risk-accounts.v1`.

## Boundary

No optimizer search change, calibration, or observed-perimeter validation. Final-period only.

## Next

Wire the report into the optimizer's risk verification path for a process scenario set.

## Pull request

PR: #TBD is queued for maintainer approval. Do not merge without approval.
