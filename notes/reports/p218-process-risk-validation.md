# P218 report: process fire-risk train/validation

Date: 2026-11-15
Phase: P218 (#1271)
Branch: `feature/p218-process-risk-validation`
Design note: `notes/design/ws4-process-risk-validation.md`

## Result

Process fire-risk reports now support a deterministic train/validation split and a stable
generalization-gap artifact.

## Evidence

- Tests: 11 passed in `tests/test_process_fire_risk.py`.
- 0.5 split on four scenarios: train `a,b`, validation `c,d`.
- Gap equals validation objective minus training objective.
- Artifact writes train/validation CSVs and JSON.
- Invalid fractions and too-few scenarios fail.
- Full dashboard: **OVERALL: GREEN**.

## Boundary

Deterministic id split only; final-period reports; no optimizer search change or observed-perimeter
validation.

## Next

Use the train/validation gap in the optimizer's process-risk verification output.
