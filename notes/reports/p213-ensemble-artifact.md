# P213 report: process-ensemble fire-regime artifact

Date: 2026-11-14
Phase: P213 (#1241)
Branch: `feature/p213-ensemble-artifact`
Design note: `notes/design/ws4-ensemble-fire-artifact.md`

## Result

`ProcessEnsembleResult.write_fire_regime` writes `fire_regime.json` with per-scenario P212
summaries.

## Evidence

- Ensemble tests: 9 passed.
- Two-scenario artifact: top-level schema and both scenario keys present.
- Each scenario's burned area and fire count match the in-memory summary.
- Zero-fire artifact: count 0, FRI `None`.
- Full dashboard: **OVERALL: GREEN**.

## Boundary

Distributional report only. No observed-perimeter validation, calibration, or optimizer risk
integration.

## Next

Use the artifact in the ensemble report and optimizer risk reporting.
