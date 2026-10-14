# ADR 0007: The optimization stack is layered and pluggable

Status: accepted
Date: 2026-10-14
Issues: TBD

## Context

The lab already runs three metaheuristics (simulated annealing, tabu search, iterated local search) and
three tuners (random, grid, Bayesian) in the FHOPS project, built on a shared neighbourhood-operator
registry and a telemetry store. WS4 needs the same capability for a different problem (a spatially
explicit forest estate model). Copying the toolkit would fork it; inventing a new one would discard
proven code and telemetry.

## Decision

Adopt a layered optimization stack: problem and objective (weighted goal programming), neighbourhood
operators, metaheuristics, a portfolio/adaptation layer, and a tuning layer, all over a shared
telemetry store. Generalize the lab's toolkit into a solver core parameterized by a problem adapter.
WS4, WS3, and FHOPS each supply an adapter. The layers and the telemetry are the same code everywhere.

## Consequences

- One toolkit to maintain, test, and tune, instead of three.
- A new metaheuristic, operator, or tuner lands once and is available to every adapter.
- The adapter boundary must be well defined: objective, feasibility, move application, and scenario
  descriptors.
- The solver core becomes a dependency of WS4, so its interface and release cadence matter.

## Alternatives considered

- **Copy FHOPS's solvers into WS4.** Rejected: forks the toolkit and its telemetry.
- **Write a WS4-specific optimizer.** Rejected: discards proven code and repeats known work.
- **One monolithic optimizer.** Rejected: a layered stack lets the portfolio and tuning layers treat
  metaheuristics as interchangeable parts.
