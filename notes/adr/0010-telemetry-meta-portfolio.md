# ADR 0010: Telemetry-driven tuning and a meta-meta-heuristic portfolio

Status: accepted
Date: 2026-10-14
Issues: TBD

## Context

A single metaheuristic with hand-tuned parameters performs unevenly across scenario families, and each
family needs a different operator mix and budget. The lab's FHOPS telemetry store already records
configuration, trajectories, operator statistics, and scenario descriptors, and its tuners (random,
grid, Bayesian) already consume it.

## Decision

Make telemetry the substrate for tuning and for a meta-meta-heuristic portfolio. Every run records a
structured record. A portfolio layer selects and steers metaheuristics across runs, adapts operator
weights online, shares elites, and recommends stopping budgets from a fitted convergence model. An
ML-boosted layer adds surrogate tuning and cross-scenario meta-learning once enough runs exist.

## Consequences

- Robustness across scenario families improves without per-family hand-tuning.
- The system depends on a consistent telemetry schema and enough runs to learn from.
- Operator-weight adaptation and portfolio selection must remain inspectable, or a result becomes hard
  to explain.
- Reproducibility requires recording the seed, the portfolio policy, and the adaptation state.

## Alternatives considered

- **Hand-tuned fixed presets.** Rejected: brittle across families and labour-intensive.
- **A single Bayesian tuner only.** Rejected: tuning one solver is not the same as choosing among
  solvers and adapting within a run.
- **Learned policies from the start.** Rejected: meta-learning needs a populated telemetry store first.
