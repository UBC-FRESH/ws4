# Process fire-risk evaluation report

Status: implemented (P215)
Phase: P215 (#1253)
Date: 2026-11-14
Related: `notes/design/ws4-fire-risk-accounts.md`,
`ws4/opt/fire_risk.py`

## 1. Purpose

P214 turns process fire-regime summaries into account rows. P215 risk-aggregates those rows with
the existing optimizer objective and returns a report.

This is a process-side counterpart to the account-overlay `RiskEvaluation`.

## 2. API

`evaluate_process_fire_risk` takes:

- per-scenario P212 summaries;
- simulation years;
- risk-aggregated `Target` values;
- optional scenario ids and weights.

It returns `ProcessFireRiskReport` with:

- per-scenario account rows;
- risk pseudo-account rows;
- effective targets;
- the weighted objective.

## 3. Exact evidence

A mean target on `fire.regime.annual_burn_rate` with a zero minimum gives objective 0. Raising the
minimum by 2 above the aggregated value gives objective 2.

## 4. Boundary

- No optimizer search change.
- No observed-perimeter validation.
- No calibration.
- Final-period only.

## 5. Limits

- The report is only as good as the process fire-regime distribution.
- The account names are a new optimizer interface.
- Multi-period fire accounting remains future work.
