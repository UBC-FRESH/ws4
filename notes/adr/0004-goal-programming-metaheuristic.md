# ADR 0004: Weighted goal programming with a parallel metaheuristic search

Status: accepted
Date: 2026-10-14
Issues: TBD

## Context

Forest planning objectives are soft and conflicting: maintain a wood flow, keep openings small, protect
habitat, control cost. Analysts express these as targets with a desired range, not as hard constraints.
Spatial structure makes the problem non-linear and combinatorial, and an exact mixed-integer
formulation of a full landscape over a long horizon is usually intractable.

## Decision

Formulate objectives as weighted goal programming: each target penalizes shortfall below its minimum
and excess above its maximum, per period, scaled by weights and an optional discount rate, with linear
or quadratic scaling. Search for a schedule with a parallel metaheuristic: multi-start, toggle, shift,
swap, and patch-coherent neighbourhoods, threshold-acceptance or annealing acceptance, checkpointing,
and a convergence criterion.

## Consequences

- Analysts express objectives in the vocabulary they already use (minimums, maximums, weights).
- The search handles spatial and non-linear structure that an exact formulation cannot.
- There is no optimality guarantee; results depend on search budget and seed. Runs are reproducible
  from their seed.
- The optimizer is parallel by construction, which suits multi-core hosts.

## Alternatives considered

- **Exact mixed-integer programming.** Rejected as the default: tractable only for reduced problems and
  awkward with spatial structure; kept in mind for a linear subset.
- **LP relaxation with rounding.** Rejected: rounding breaks spatial constraints and target tolerances.
- **Greedy construction only.** Rejected: brittle and easily trapped in poor local solutions.
