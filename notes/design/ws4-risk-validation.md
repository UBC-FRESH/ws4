# Multi-fidelity risk validation

Status: implemented (P182)
Phase: P182 (#1074)
Date: 2026-11-13
Related: `notes/design/ws4-risk-optimization.md`, `ws4/opt/risk.py`,
`ws4/opt/engine.py`

## 1. Problem

P181 evaluates risk-aggregated targets during the search with a fast account overlay. The
inner search may use incremental values; the final incumbent is re-simulated and evaluated on
the full account frame. Those two objectives should not be assumed equal.

P182 makes the difference visible and adds an out-of-sample train/validation risk report.

## 2. Search-versus-full verification

When a scenario file is active, `Optimizer.run` writes `risk_verification.json`:

```json
{
  "search_objective": 12.5,
  "full_objective": 13.1,
  "gap": 0.6
}
```

`search_objective` is the best objective from the search. `full_objective` is the final
`RiskEvaluation` on the full simulator account frame. A non-zero gap is reported, not hidden or
silently corrected by changing the incumbent.

## 3. Train/validation report

`risk_validation_fraction` splits the scenario ensemble in order:

- training scenarios first;
- validation scenarios last;
- at least one scenario in each set.

`evaluate_risk_validation` runs `RiskAccountEvaluator` on both subsets and writes:

- `risk_train_values.csv`;
- `risk_validation_values.csv`;
- `risk_train_aggregated.csv`;
- `risk_validation_aggregated.csv`;
- `risk_validation.json` with objectives and the generalization gap.

The gap is validation objective minus training objective. With one scenario, the optimizer
writes `risk_validation.json` with `status: skipped` and the reason.

## 4. CLI

```bash
ws4 optimize ... --scenario-file scenarios.yaml --risk-validation-fraction 0.7
```

The fraction must be between zero and one. It requires a scenario file. The option is off by
default, so the deterministic and P181 paths are unchanged.

## 5. Limits

- Both fidelities are still account overlays; neither runs the process engine per candidate.
- The split is ordered, not random. Scenario files should be ordered to avoid a systematic
  train/validation bias.
- A one-scenario ensemble cannot provide an out-of-sample report.
- The gap is a diagnostic, not a convergence guarantee.
- Multi-fidelity search (low-fidelity candidates, high-fidelity elites) remains later work.
