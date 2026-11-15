# P218 close-out: process fire-risk train/validation

Date: 2026-11-15
Phase: P218 (#1271)
Branch: `feature/p218-process-risk-validation`
Tasks: P218.1 (#1272), P218.2 (#1273)
Design note: `notes/design/ws4-process-risk-validation.md`
Report: `notes/reports/p218-process-risk-validation.md`

## Result

Process fire-risk reports now support a deterministic train/validation split and a stable
generalization-gap artifact.

## What changed

- `ProcessFireRiskValidation`.
- `evaluate_process_fire_risk_validation`.
- Train/validation CSV and JSON writer.
- Three tests for split, artifact, and invalid inputs.

## Evidence

- Tests: 11 passed in `tests/test_process_fire_risk.py`.
- 0.5 split on four scenarios: train `a,b`, validation `c,d`.
- Gap equals validation objective minus training objective.
- Full dashboard: **OVERALL: GREEN** on all seven gates.

## Boundary

Deterministic id split only; final-period reports; no optimizer search change or observed-perimeter
validation.

## Next

Use the train/validation gap in the optimizer's process-risk verification output.

## Pull request

PR: #TBD is queued for maintainer approval. Do not merge without approval.
