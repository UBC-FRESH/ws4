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

## Current state

- FHOPS supplies the second adapter with its machine-by-slot schedule and its existing repair and
  incremental evaluators. Kernel SA, Tabu, ILS, and a dirty-repair fast path are in place.
- The generic telemetry logger and the `Runner` protocol are in the kernel. WS4's portfolio and
  tuning orchestration remain local because they depend on `OptimizeConfig`, `Optimizer`,
  `Target`, and the run-directory contract.
- Behaviour parity with FHOPS's existing SA/Tabu/ILS loops is not yet claimed; the next gate is
  like-for-like scenario and performance evidence.

## Telemetry, portfolio, and tuning boundary

- `ws4.opt.telemetry` is now a re-export of `fresh_solutions.kernel.telemetry`. The logger is
  generic (run header, step, trace, target values, changed-schedule snapshots) and has no WS4
  imports.
- `ws4.opt.portfolio` and `ws4.opt.tune` stay in WS4. They orchestrate `OptimizeConfig`,
  `Optimizer`, `Target`, and WS4's run directory contract; moving them before the kernel has a
  generic runner/config contract would only add indirection. Revisit after the FHOPS adapter
  proves the cross-package orchestration boundary.
- `ws4.opt.portfolio` and `ws4.opt.tune` now import the shared `Runner` protocol from
  `fresh_solutions.kernel`. Their configuration, target scaling, and run-directory orchestration
  stay in WS4.
