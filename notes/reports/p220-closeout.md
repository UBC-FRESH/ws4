# P220 close-out: combined risk verification bundle

Date: 2026-11-15
Phase: P220 (#1276)
Branch: `feature/p220-risk-bundle`
Tasks: P220.1 (#1277), P220.2 (#1278)
Design note: `notes/design/ws4-risk-bundle.md`
Report: `notes/reports/p220-risk-bundle.md`

## Result

The optimizer risk summary and P218 process risk train/validation can now be written into one
stable JSON bundle.

## What changed

- `write_risk_verification_bundle`.
- `risk_verification_bundle.json` with schema `ws4.risk-verification-bundle.v1`.
- Two tests covering content and invalid input.
- Reference and design documentation.

## Evidence

- Tests: 13 passed in `tests/test_process_fire_risk.py`.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Optimizer summary preserved unchanged.
- Process gap preserved exactly.
- Empty optimizer summary rejected.

## Boundary

The bundle does not run either engine or introduce a combined decision rule. No calibration or
observed-perimeter validation.

## Next

Use the bundle in the optimizer's risk verification output path.

## Pull request

PR: #TBD is queued for maintainer approval. Do not merge without approval.
