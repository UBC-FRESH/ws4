# ADR 0003: Spatial structure is part of the model

Status: accepted
Date: 2026-10-14
Issues: TBD

## Context

An aspatial estate model solves for "how much" and leaves "where" to a later allocation step. That
allocation cannot respect adjacency, opening size, green-up, or access at solve time, because those
relationships were not in the problem. The result is a schedule that looks feasible on paper and is
infeasible on the ground, or a costly repair step.

## Decision

Make spatial structure first-class. Adjacency is a table (a block-to-block topology). Patch metrics and
patch objectives, core and edge handling, and road access and haul cost are subsystems that participate
in simulation and optimization. A schedule is evaluated with its spatial consequences in the loop.

## Consequences

- Feasible, defensible schedules: adjacency, opening size, and access are enforced where decisions are
  made.
- The objective function and the neighbourhood moves must understand space, which makes the search
  harder and the code larger.
- The compiled dataset carries topology and route tables, so compilation has more to do.
- A purely aspatial run remains possible by supplying an empty topology and no route model.

## Alternatives considered

- **Keep allocation post-hoc.** Rejected: it cannot enforce constraints the solver never saw, which is
  the problem WS4 exists to solve.
- **Enforce spatial constraints only in a repair pass.** Rejected: repair is fragile, and it still
  cannot guarantee feasibility.
