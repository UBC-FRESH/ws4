# P212 close-out: process-ensemble fire-regime report

Date: 2026-11-14
Phase: P212 (#1232)
Branch: `feature/p212-process-fire-regime`
Tasks: P212.1 (#1233), P212.2 (#1234), P212.3 (#1235)
Design note: `notes/design/ws4-process-fire-regime.md`
Report: `notes/reports/p212-process-fire-regime.md`

## Result

`ProcessEnsembleResult` now exposes per-scenario fire-regime summaries derived from the P188
event-log risk layer.

## What changed

- `ProcessEnsembleResult.fire_regime_summaries`.
- Two integration tests:
  - summary totals match annual burned-area values;
  - zero-fire ensembles are valid.
- Reference and design documentation.

## Evidence

- Ensemble tests: 7 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Two scenarios: both summaries present; totals match.
- Zero fire: count 0, burned area 0, FRI `None`.

## Boundary

Distributional process report only. Not an observed-perimeter comparison, not calibration, and
not a replacement for the P181 account-overlay risk path.

## Next

Use the summaries in the ensemble report, then connect them to optimizer risk reporting.

## Pull request

PR: #TBD is queued for maintainer approval. Do not merge without approval.
