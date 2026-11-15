# P221 close-out: optimizer risk verification bundle

Date: 2026-11-15
Phase: P221 (#1281)
Branch: `feature/p221-optimizer-bundle`
Tasks: P221.1 (#1282), P221.2 (#1283)
Design note: `notes/design/ws4-optimizer-risk-bundle.md`
Report: `notes/reports/p221-optimizer-bundle.md`

## Result

An optimizer output directory can now receive the combined optimizer/process risk bundle directly
from its written `risk_verification.json`.

## What changed

- `bundle_existing_risk_verification`.
- Reads and validates the optimizer verification file.
- Writes `risk_verification_bundle.json` in the same directory.
- Two tests for success and missing-file failure.

## Evidence

- Tests: 15 passed in `tests/test_process_fire_risk.py`.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Optimizer values preserved.
- Process train/validation gap preserved.
- Missing optimizer verification fails.

## Boundary

The optimizer and process runs remain separate; no combined decision rule. No calibration or
observed-perimeter validation.

## Next

Call the bundle after an optimizer run that has an associated process-risk validation.

## Pull request

PR: #TBD is queued for maintainer approval. Do not merge without approval.
