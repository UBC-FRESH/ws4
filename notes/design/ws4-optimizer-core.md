# Optimizer core: event chains and move-based evaluation

Status: **proposed** (issues #78, #79). Not started.

Related: `notes/design/ws4-optimization-stack.md`, `notes/design/ws4-performance.md`,
`docs/reference/optimizer.rst`.

## 1. Two gaps found using the watcher (`ws4 watch`, P6.16)

**Correctness (#78).** The simulator treats a block as many times as the schedule asks, but the
optimizer's schedule is `dict[block, (treatment, year)]` — one treatment per block — and
`candidates()` reads only the block's initial track. A block can never be harvested a second time in
the horizon. On a 200-year C5 horizon this caps the harvest (each block once) and blocks any
even-flow above ~0.97 Mm3/period. Evidence: block 35, `CC` at year 0 and 40, produces products in
both years. Nothing documents the one-treatment rule; it is an implementation simplification.

**Speed (#79).** `_incremental_values` merges every block's delta into the schedule totals on every
evaluation — O(schedule x years x accounts) per move. Profile on C5 (50-year, 5,648 blocks, 5 warm
evaluations): 4.39 s total, of which `_incremental_values` is 2.59 s and 9.78 M `dict.get` calls are
1.71 s; `objective` is 0.023 s. That is ~880 ms/evaluation, ~1 move/s, against the reference tool's
~1000 moves/s. The gap is structural, not a constant factor.

## 2. Proposal: one redesign of the optimizer core

Do both together, because both change the same boundary.

### 2.1 The centrepiece: a per-move objective delta (dZ)

The evaluator must answer, for a candidate move, **what does the objective change by** — and nothing
else. Keep the objective's *state* and update it by the move's delta:

- **State.** The realized totals per (year, account) for the **target accounts only** (usually one or
  two), plus the cached per-period penalty. Not all ~20 accounts, not the whole account frame.
- **Per-block contributions.** Each candidate chain has a contribution: the values it adds per
  (year, account). Cached per chain, stored sparsely (`year -> value`) or as a dense array over the
  years.
- **dZ of a move on block b**, from its old chain's contribution `old` to a new chain's `new`:

      dZ = sum over (year, account) cells that change:
             penalty(total[cell] - old[cell] + new[cell]) - penalty(total[cell])

  The penalty is piecewise linear in the total (shortfall + excess against fixed levels), so this is
  **exact**, and it costs O(cells the block touches) — not O(schedule). Untouched years, accounts,
  and blocks are never visited.
- **Accept** applies the contribution to the state; **reject** discards it. Because the objective is
  separable across its (year, account) cells, the move's delta is the sum over the cells it changes.

This is what turns ~2M dict updates per move into a few hundred numpy operations over the affected
cells: a block's chain spans `years` cells per account, so a 200-year move is ~200 cells, sub-ms.

The same treatment applies to the rest of Z:
- **spatial penalty** — only the moved block and its neighbours (already scoped by `_incident_edges`);
- **route accounts** — only the moved block's routed products and the segments they use.

### 2.2 The schedule it operates on

- **Schedule = an ordered event chain per block.** `dict[int, tuple[Event, ...]]` with
  `Event = (treatment, year)`, ordered by year. `candidates()` walks the track transitions from the
  block's initial state, generating the feasible rotations (each treatment's age window, offset by
  the previous transition), up to a rotation cap derived from the horizon. The empty chain is a
  candidate.
- **Operators mutate chains.** Toggle adds/removes a rotation, shift moves an event's year within
  its window, swap exchanges two blocks' chains, LNS destroys/repairs events. Each returns the set
  of changed blocks (the solver already computes a move signature), so the evaluator is handed
  exactly the moves to price.

### 2.3 Representation of the contributions

Store a contribution as a small array indexed by (year, account-slot) so updates are slice
operations, not dict churn. This is the seam where a compiled kernel (P6.6, deferred) would later
slot in: the dZ loop is a handful of vectorised array ops.

## 3. Spatial and route accounts

- `schedule_years` (`ws4/patch/constraints.py`) currently keeps the *first* disturbance year per
  block; with chains it must keep every disturbance year, and the green-up rule must consider
  successive rotations of a block and its neighbours.
- `block_route_accounts` and `block_trajectory` take one treatment; both take a chain.
- The incremental route accounts (P6.10) stay additive per block.

## 4. Correctness plan

- A block treated twice: simulator and optimizer agree with a two-row schedule CSV.
- **dZ is exact**: for random schedules and random moves, the summed per-move dZ equals the
  difference of the whole-schedule objective. Because the deltas are exact, a fixed seed must
  produce the **same sequence of accepted moves and the same incumbent objective** as today's
  evaluator — a strong step-by-step regression test, not just a final-value one.
- The feature/route/spatial parity tests, the nine acceptance variants, and the benchmark.

## 5. Targets

| Metric | Now | Target |
| --- | ---: | ---: |
| C5 objective evaluations per second (one core, 50 y) | ~1 | >= 1000 |
| C5 objective evaluations per second (one core, 200 y) | ~0.45 | >= 500 |
| Even flow reachable, 200 y | one pass (~0.97 Mm3/period) | multi-rotation (several Mm3/period) |

## 6. Milestones

- **M1** dZ for the current one-treatment schedule: running totals over target accounts + per-move
  delta, parity (including same-seed trajectory), measure. Lands the speedup on its own.
- **M2** Chain schedule type and `candidates()`; a block is treated twice; dZ over chains.
- **M3** Spatial per-rotation disturbance years; route accounts for chains.
- **M4** Benchmarks (`scripts/benchmark.py`), docs, roadmap, changelog.

## 7. Log

- 2026-10-16: gaps found and profiled while testing `ws4 watch`; issues #78 (multi-rotation) and
  #79 (move-based objective) filed; proposal written.
- 2026-10-16 **M1 done** (issue #79): `ws4/opt/incremental.py` (`IncrementalObjective`) keeps the
  realized totals per `(year, account)` for the target accounts and prices a move by the exact
  delta; `solvers.solve_sa_delta` mirrors `solve_sa`'s acceptance; `Optimizer._solve` uses it for
  SA when there are no route/duplicate/edge extras, else falls back. A/B on C5 (50-year, 5,648-block
  schedule, 60 iterations): whole-schedule 26.80 s (2.2 iters/s) vs move-based **0.426 s
  (141 iters/s)** = **63x**, incumbent objective identical (17 458 613) and confirmed by a full
  re-evaluation. Tests: `tests/test_incremental.py` (6).
- 2026-10-16 M1 profile of what remains (per move): `evaluator.delta` **0.001 ms** and `apply`
  0.001 ms, but `operator.apply` 0.611 ms (it rebuilds the candidate block list and copies the
  schedule each call) and `_changed_blocks` 0.540 ms (O(schedule) diff). So the objective delta is
  solved; the next win is the move bookkeeping (precompute the operator block lists, have operators
  report changed blocks, avoid whole-schedule dict copies) — target ~1000 iters/s.
