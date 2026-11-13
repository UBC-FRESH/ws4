# P181 close-out: scenario and risk evaluation in the optimizer

Date: 2026-11-13
Phase: P181 (#1068)
Branch: `feature/p181-risk-optimizer`
Tasks: P181.1 (#1069), P181.2 (#1070), P181.3 (#1071), P181.4 (#1072)
Design note: `notes/design/ws4-risk-optimization.md`

## Result

The estate optimizer can now evaluate scenario and risk-aggregated targets through a fast,
auditable account-overlay path.

## What changed

- `ws4/opt/risk.py`: `apply_account_multipliers`, `RiskAccountEvaluator`, and `RiskEvaluation`.
- `OptimizeConfig.scenario_path`: loads a `ws4.scenario.v1` ensemble once.
- `Optimizer._evaluate`: risk aggregation in scenario mode; deterministic path unchanged.
- `Optimizer.last_risk_evaluation`: exposes the most recent risk state.
- `delta_evaluator` returns `None` when scenarios are active, because risk aggregation is not
  additive over blocks.
- `ws4 optimize --scenario-file`: CLI support with active-target aggregation validation.
- Run artifacts: `risk_values.csv`, `risk_aggregated.csv`, `risk_summary.json`, and a
  `risk` block in `summary.json`.
- Docs: `docs/reference/risk-optimization.rst`; optimizer reference section; design note.

## Evidence

- Risk tests: 7 passed.
- Succession/regeneration/bridge integration tests: 21 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- The synthetic-estate integration test runs a scenario optimization and checks the risk
  artifacts.
- Deterministic tests remain green when no scenario file is set.

## Calibration and model boundary

This is an **account-overlay risk model**, not a process-driven stochastic landscape simulation.
All scenarios share one deterministic estate account frame and differ only by
`account_multipliers`. Scenario seeds are recorded for provenance but do not drive process draws
in this path.

Flow targets are rejected by the risk layer. The spatial penalty is applied after the risk
objective and is not scenario-specific.

## Limits

- No per-candidate process simulation; that is too expensive for the inner search.
- No multi-fidelity search or surrogate.
- No scenario-specific spatial constraints.
- Account multipliers are a scenario assumption, not a calibrated probability model.
- Full stochastic search remains the next optimization phase.

## Next

After P179, P180, and P181 merge, add multi-fidelity or process-driven ensemble evaluation
outside the inner loop, then revisit decision-grade risk validation.

## Pull request

PR: #1073 is queued for maintainer approval. Do not merge without approval.
