# P220 report: combined risk verification bundle

Date: 2026-11-15
Phase: P220 (#1276)
Branch: `feature/p220-risk-bundle`
Design note: `notes/design/ws4-risk-bundle.md`

## Result

Optimizer and process risk verification summaries can now be written into one JSON bundle.

## Evidence

- Tests: 13 passed in `tests/test_process_fire_risk.py`.
- Bundle schema `ws4.risk-verification-bundle.v1`.
- Optimizer summary preserved unchanged.
- Process train/validation gap preserved exactly.
- Empty optimizer summary rejected.
- Full dashboard: **OVERALL: GREEN**.

## Boundary

The bundle does not run either engine or introduce a combined decision rule. No calibration or
observed-perimeter validation.

## Next

Use the bundle in the optimizer's risk verification output path.
