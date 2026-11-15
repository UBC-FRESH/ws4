# Process fire-risk report artifact

Status: implemented (P216)
Phase: P216 (#1259)
Date: 2026-11-15
Related: `notes/design/ws4-process-risk-report.md`

## 1. Purpose

P215 evaluates process fire risk in memory. P216 writes the report to a stable artifact directory
for review and later optimizer verification.

## 2. Contract

`ProcessFireRiskReport.write` writes:

- `process_fire_risk_values.csv`;
- `process_fire_risk_aggregated.csv`;
- `process_fire_risk.json`.

The JSON summary records:

- schema `ws4.process-fire-risk-accounts.v1`;
- scenario ids;
- aggregated account count;
- effective target accounts;
- objective.

An empty report is rejected.

## 3. Evidence

`tests/test_process_fire_risk.py`:

- writes a two-scenario report;
- checks scenario ids, target account, objective 0;
- checks both CSV files exist;
- rejects an empty report.

## 4. Limits

- Final-period report only.
- No optimizer search integration.
- Distributional, not observed-perimeter validation.
