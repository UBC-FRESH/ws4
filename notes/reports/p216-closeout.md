# P216 close-out: process fire-risk report artifact

Date: 2026-11-15
Phase: P216 (#1259)
Branch: `feature/p216-risk-report-artifact`
Tasks: P216.1 (#1260), P216.2 (#1261)
Design note: `notes/design/ws4-process-risk-artifact.md`
Report: `notes/reports/p216-risk-report-artifact.md`

## Result

The P215 process fire-risk report now writes a stable artifact directory.

## What changed

- `ProcessFireRiskReport.write`.
- `process_fire_risk_values.csv`.
- `process_fire_risk_aggregated.csv`.
- `process_fire_risk.json` with scenarios, targets, and objective.
- Empty-report rejection.
- Tests and documentation.

## Evidence

- Process fire-risk tests: 8 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Two-scenario artifact: schema, scenarios, target account, objective verified.
- Empty report rejected.

## Boundary

Final-period report only. No optimizer search integration, calibration, or observed-perimeter
validation.

## Next

Use the report artifact in the optimizer's risk verification path for a process scenario set.

## Pull request

PR: #TBD is queued for maintainer approval. Do not merge without approval.
