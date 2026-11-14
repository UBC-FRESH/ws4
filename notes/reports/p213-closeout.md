# P213 close-out: process-ensemble fire-regime artifact

Date: 2026-11-14
Phase: P213 (#1241)
Branch: `feature/p213-ensemble-artifact`
Tasks: P213.1 (#1242), P213.2 (#1243)
Design note: `notes/design/ws4-ensemble-fire-artifact.md`
Report: `notes/reports/p213-ensemble-artifact.md`

## Result

The process ensemble can now write its per-scenario fire-regime summaries to a stable JSON
artifact alongside the existing process artifacts.

## What changed

- `ProcessEnsembleResult.write_fire_regime`.
- `fire_regime.json` with schema `ws4.process-fire-regime.v1`.
- Two tests: two-scenario artifact and zero-fire artifact.
- Reference and design documentation.

## Evidence

- Ensemble tests: 9 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Artifact scenario keys and totals match the in-memory summaries.
- Zero-fire artifact is valid JSON with count 0 and null FRI.

## Boundary

Distributional report only. No observed-perimeter validation, calibration, or optimizer risk
integration.

## Next

Use the artifact in the ensemble report and optimizer risk reporting.

## Pull request

Merged as `58fa941` (PR #1245); branch deleted.
