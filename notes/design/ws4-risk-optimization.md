# Risk-aware estate optimization

Status: implemented (P181)
Phase: P181 (#1068)
Date: 2026-11-12
Related: `notes/design/ws4-stochastic-landscape.md`,
`notes/design/ws4-process-executor.md`, `ws4/opt/risk.py`, `ws4/opt/engine.py`,
`ws4/ecosystem/scenarios.py`

## 1. Purpose

P144 defined scenario ensembles and risk targets. P181 connects them to the estate optimizer
with a fast, inspectable path:

```text
one deterministic account frame × scenario account multipliers
    -> per-scenario values
    -> risk aggregation
    -> weighted-goal objective
```

This is an **account-overlay risk model**, not a stochastic landscape simulation. It is a
bridge that lets the planner test risk-aggregated targets now; process-driven scenario
simulation and multi-fidelity search are later work.

## 2. Scenario file

The optimizer accepts the existing `ws4.scenario.v1` file. The overlay interprets one override:

```yaml
schema_version: ws4.scenario.v1
scenarios:
  - scenario_id: low
    seed: 1
    overrides:
      account_multipliers:
        feature.Volume: 0.8
  - scenario_id: high
    seed: 2
    overrides:
      account_multipliers:
        feature.Volume: 1.2
```

The seed is retained for provenance and future process-driven scenarios. In the overlay path
it does not change the deterministic account frame.

## 3. Risk evaluator

`ws4.opt.risk.apply_account_multipliers` scales only the named accounts and stamps the scenario
id. `RiskAccountEvaluator` concatenates the per-scenario frames and calls the existing
`risk_account_values` function. The returned `RiskEvaluation` contains:

- per-scenario values;
- risk pseudo-account rows;
- effective targets (the original target points at the `risk.*` pseudo-account);
- the weighted-goal objective.

Mean, min, max, CVaR, quantile, probability, and regret are available through the existing
target aggregation fields. Flow targets are rejected by the risk layer.

## 4. Optimizer integration

`OptimizeConfig.scenario_path` loads the ensemble once. When it is set:

- `Optimizer._evaluate` uses `RiskAccountEvaluator` on the normal account frame;
- the objective is the risk-aggregated weighted-goal penalty plus the spatial penalty;
- `delta_evaluator` returns `None`, because risk aggregation is not additive over blocks;
- the last `RiskEvaluation` is available through `last_risk_evaluation`.

When no scenario file is set, the deterministic path is unchanged. Risk-aggregated targets
without a scenario file fail with a named error.

## 5. CLI

```bash
ws4 optimize ... --scenario-file scenarios.yaml
```

The CLI validates that every active target uses non-single aggregation. The run uses the
same schedule search; only the objective evaluation changes.

## 6. Limits

- This is not a process-driven stochastic simulation. All scenarios share one deterministic
  estate frame and differ only by account multipliers.
- Scenario seeds are recorded but do not drive draws in this path.
- The full stochastic ensemble evaluation (run the process engine per candidate) is too
  expensive for the inner search; multi-fidelity evaluation is the next step.
- Flow targets cannot be risk-aggregated.
- The spatial penalty is applied after the risk objective; it is not scenario-specific.

## 7. Verification

- Account multiplier arithmetic and unknown-account rejection.
- Mean and shortfall objective checks.
- Single-aggregation rejection.
- Optimizer integration on the synthetic estate: scenario file, risk objective, last risk
  evaluation, and delta-evaluator bypass.
- Deterministic runs remain unchanged when no scenario file is set.
