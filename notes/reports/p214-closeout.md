# P214 close-out: process fire-regime risk accounts

Date: 2026-11-14
Phase: P214 (#1246)
Branch: `feature/p214-fire-risk-accounts`
Tasks: P214.1 (#1247), P214.2 (#1248), P214.3 (#1249)
Design note: `notes/design/ws4-fire-risk-accounts.md`
Report: `notes/reports/p214-fire-risk-accounts.md`

## Result

Per-scenario process fire-regime summaries now map to optimizer account rows and feed the existing
risk aggregation.

## What changed

- `ws4/opt/fire_risk.py`:
  - `fire_regime_account_values`;
  - stable account names;
  - zero-fire FRI omission.
- Four tests covering complete rows, risk aggregation, zero fire, and invalid inputs.
- Reference and design documentation.

## Evidence

- Process fire-risk tests: 4 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Two-scenario totals match.
- Mean risk target produces `risk.mean.0.fire.regime.annual_burn_rate`.

## Boundary

Final-period reporting bridge only. No optimizer search change, calibration, or observed-perimeter
validation.

## Next

Add a process-conditioned scenario set to the optimizer's risk evaluation.

## Pull request

PR: #1252 is queued for maintainer approval. Do not merge without approval.
