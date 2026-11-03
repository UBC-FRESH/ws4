# Shared search kernel adoption

Status: active (2026-11-03)
Related: ADR 0007, `notes/design/ws4-optimization-stack.md`

## Decision

WS4 consumes the problem-agnostic search kernel from `fresh-solutions` instead of maintaining a
second copy of the operator registry, solvers, cooling schedules, and stopping rules. WS4 keeps the
domain layer: the compiled dataset, `Optimizer`, goal-programming targets, incremental accounting,
constraints, patch/spatial/route/carbon models, MIP bounds, seeding, and run reporting.

The kernel boundary is a generic `Problem[State, Context]`:

- `State` is adapter-owned; WS4 uses `dict[block, Chain]`.
- `Context` is adapter-owned; WS4 uses the candidate chains.
- operators mutate the state in place and return an undo record.
- the kernel supplies SA, delta-SA, tabu, ILS, threshold, cooling, patience/reversion/time limits,
  and control files.

## What changed

- `ws4.opt.core.Problem` subclasses `fresh_solutions.kernel.Problem` and fixes the WS4 state and
  context types, the `dict` empty state, and the `dict` clone.
- `ws4.opt.solvers` re-exports the kernel solvers. The delta wrapper keeps WS4's `None`-means-empty
  starting schedule.
- `ws4.opt.cooling` and `ws4.opt.control` re-export the kernel implementations.
- `ws4.opt.operators` imports `Operator`, `OperatorRegistry`, and `restore` from the kernel; the WS4
  operators remain local.

## Next

- FHOPS supplies the second adapter with its machine-by-slot schedule and its existing repair and
  incremental evaluators.
- Telemetry and portfolio/tuning unification follows after the FHOPS adapter proves the boundary.
