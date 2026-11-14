# P214 report: process fire-regime risk accounts

Date: 2026-11-14
Phase: P214 (#1246)
Branch: `feature/p214-fire-risk-accounts`
Design note: `notes/design/ws4-fire-risk-accounts.md`

## Result

Process fire-regime summaries now map to optimizer account rows and feed the existing risk
aggregation.

## Evidence

- Tests: 4 passed.
- Two-scenario ensemble: account rows complete, totals match.
- Zero-fire case: FRI omitted, fire count 0.
- Mean risk target produces `risk.mean.0.fire.regime.annual_burn_rate`.
- Full dashboard: **OVERALL: GREEN**.

## Boundary

Final-period reporting bridge only. No optimizer search change, calibration, or observed-perimeter
validation.

## Next

Add a process-conditioned scenario set to the optimizer's risk evaluation.
