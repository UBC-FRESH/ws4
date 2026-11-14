# P212 report: process-ensemble fire-regime report

Date: 2026-11-14
Phase: P212 (#1232)
Branch: `feature/p212-process-fire-regime`
Design note: `notes/design/ws4-process-fire-regime.md`

## Result

`ProcessEnsembleResult` now exposes `fire_regime_summaries`, which runs the P188 event-log summary
over each scenario's replayable log.

## Evidence

- `tests/test_ecosystem_ensemble.py`: 7 passed.
- Two-scenario ensemble: both summaries present.
- Each summary's total burned area equals the scenario's summed annual `fire.burned_area_ha`.
- Zero-fire ensemble: fire count 0, burned area 0, FRI `None`.
- Full dashboard: **OVERALL: GREEN**.

## Boundary

Distributional process report only. Not an observed-perimeter comparison, not calibration, and
not a replacement for the P181 account-overlay risk path.

## Next

Use the per-scenario summaries in the ensemble report, then connect them to optimizer risk
reporting.
