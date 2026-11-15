# Process fire-risk train/validation

Status: implemented (P218)
Phase: P218 (#1271)
Date: 2026-11-15
Related: `notes/design/ws4-process-risk-report.md`

## 1. Purpose

P215 evaluates process fire risk in memory. P218 splits process scenarios into training and
validation subsets and reports the generalization gap.

## 2. Split

Scenarios are sorted by id. The first `floor(n * train_fraction)` scenarios train; the rest
validate, with at least one scenario on each side. The split is deterministic.

## 3. Report

`ProcessFireRiskValidation` carries:

- training and validation `ProcessFireRiskReport` values;
- train fraction;
- validation objective minus training objective.

`write` emits training and validation account CSVs plus a JSON summary.

## 4. Evidence

- Four scenarios, 0.5 split: train `a,b`; validation `c,d`.
- Gap equals validation objective minus training objective.
- Artifact JSON records scenario ids, objectives, and gap.
- Invalid fractions and fewer than two scenarios fail.

## 5. Limits

- Deterministic id split, not random resampling.
- Final-period only.
- No optimizer search change or observed-perimeter validation.
