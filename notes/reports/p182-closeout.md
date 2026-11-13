# P182 close-out: multi-fidelity risk validation

Date: 2026-11-13
Phase: P182 (#1074)
Branch: `feature/p182-risk-validation`
Tasks: P182.1 (#1075), P182.2 (#1076), P182.3 (#1077), P182.4 (#1078)
Design note: `notes/design/ws4-risk-validation.md`

## Result

P182 makes the gap between the search risk objective and the final full-simulation risk
objective visible, and adds an out-of-sample train/validation risk report.

## What changed

- `RiskValidationReport`, `split_scenarios`, and `evaluate_risk_validation` in
  `ws4/opt/risk.py`.
- `risk_verification.json` compares `search_objective`, `full_objective`, and `gap`.
- `--risk-validation-fraction` writes train/validation risk files for the incumbent.
- One-scenario ensembles write a `skipped` report with the reason.
- Summary `risk` block carries verification and validation state.
- Docs and design note.

## Evidence

- Risk tests: 9 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- The synthetic-estate run writes `risk_verification.json`, `risk_validation.json`,
  `risk_train_values.csv`, and `risk_validation_values.csv`.
- The deterministic path is unchanged when the validation fraction is off.

## Limits

- Both fidelities are account overlays; neither runs the process engine per candidate.
- The train/validation split is ordered, not random.
- One scenario cannot provide an out-of-sample report.
- A non-zero verification gap is a diagnostic, not a convergence guarantee.
- Multi-fidelity search (low-fidelity candidates, high-fidelity elites) remains later work.

## Recommendation

Do not treat the overlay as process-driven stochastic simulation. After the P179–P182 stack
merges, the next step is process-driven ensemble evaluation outside the inner loop or a
documented high-fidelity elite pass.

## Pull request

PR: #1079 is queued for maintainer approval. Do not merge without approval.
