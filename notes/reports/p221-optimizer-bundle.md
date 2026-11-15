# P221 report: optimizer risk verification bundle

Date: 2026-11-15
Phase: P221 (#1281)
Branch: `feature/p221-optimizer-bundle`
Design note: `notes/design/ws4-optimizer-risk-bundle.md`

## Result

An optimizer output directory can now receive the combined optimizer/process risk bundle directly
from its written `risk_verification.json`.

## Evidence

- Tests: 15 passed in `tests/test_process_fire_risk.py`.
- Optimizer values preserved.
- Process train/validation gap preserved.
- Missing optimizer verification fails.
- Full dashboard: **OVERALL: GREEN**.

## Boundary

The optimizer and process runs remain separate; no combined decision rule. No calibration or
observed-perimeter validation.

## Next

Call the bundle after an optimizer run that has an associated process-risk validation.
