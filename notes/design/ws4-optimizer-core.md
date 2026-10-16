# Optimizer core: event chains and move-based evaluation

Status: **done** (issues #78, #79). Merged to `feature/p6-performance`.

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
- 2026-10-16 **M1b done** (issue #79): the objective delta was already ~1 us; the rest was
  bookkeeping. Fixes: the LNS destroy used a *list* membership test (`block not in destroyed` over
  ~565 items x 5,648 blocks -> 32 ms/call -> 1.0 ms with a set); a shared operator option index
  (assignable blocks, shiftable options) removed per-call scans (toggle 0.50 -> 0.08 ms, shift
  1.83 -> 0.70 ms); `Simulator.block_products` computes only the products at the treatment year and
  `Optimizer._block_delta(..., accounts)` uses it when the targets are product accounts, so a cache
  miss costs O(fragments) not O(fragments x years). Measured on C5 (50-year): cold reset
  13.4 -> **0.9 s**; steady state 39.8 -> **443 iters/s**; whole-schedule ~2.2 iters/s, so ~200x.
  Correctness: 300-path comparison and a 60-move random walk are exact (0 mismatch); the A/B
  incumbent matches a full re-evaluation and follows the same trajectory.
- 2026-10-16 the watcher now uses the delta evaluator (`run_watch` builds it via
  `delta_evaluator(targets, watched_accounts)`), so `ws4 watch` is on the fast path too: 1000
  iterations in ~3.1 s on C5 (50-year).
- Bug found and fixed on the way: the new `block_products` fast path must use the fragment's offset
  *at the treatment year* (the simulator ages the fragment `year` steps), i.e. `offset + year`;
  without it the delta under-reported and the search diverged.
- 2026-10-16 **M1c done** (issue #79): operators gained `propose`, which returns the new schedule
  *and the blocks it changed*; the delta solver no longer diffs the schedule (`_changed_blocks` was
  61% of the remaining time). The shift operator samples a shiftable block in O(1) with a scan
  fallback instead of building an O(schedule) list each call. Steady state 443 -> **730 iters/s** on
  C5 (50-year); cold reset 0.8 s. Correctness unchanged (0 mismatch over a 300-move path comparison;
  347 tests). Remaining cost is flat Python/pandas overhead (dict lookups, per-call array extraction,
  LNS). To go beyond ~1000 iters/s the state would move to numpy arrays with an optional compiled
  kernel (P6.6).
- 2026-10-16 **M2a done** (issue #78): `Simulator.block_chain(block, events, years)` evaluates a
  block under a *sequence* of treatments (rotations), and `block_trajectory` is now a one-event
  chain. This is the per-chain contribution the optimizer's delta will price. Verified: a one-event
  chain equals `block_trajectory`; a two-event chain's delta equals a full `simulate` of the same
  rows (fixture worst diff 0.000000 with the product cell present; C5 worst 0.000000). Next (M2b):
  candidates as feasible chains (walk the track transitions), a chain schedule type, and operators +
  delta over chains; then (M2c) spatial disturbance years per rotation and route accounts for a
  chain.
- 2026-10-16 **M2b done** (issue #78): the optimizer now searches chains. `Schedule` is
  `dict[int, Chain]` (a block's ordered events); `candidates()` walks the track transitions to
  generate the feasible rotations (window start/mid/end per rotation, capped at 3 rotations and 12
  chains per block); `_schedule_frame` expands a chain to rows; `_block_delta(block, chain)` evaluates
  a chain (with the `block_chain_products` fast path); the delta evaluator prices a changed block's
  whole chain; the operators toggle/rechoose/swap/destroy chains. Verified on C5 (200-year): 6,169 of
  12,567 blocks have multi-rotation candidates (e.g. block 35 -> `(('CC', 28), ('CC', 178))`), a mixed
  chain schedule's incremental values equal a full simulation exactly (0.000000), and SA built an
  incumbent with 1,060 multi-rotation blocks. Remaining (M2c): spatial disturbance years per rotation,
  route accounts for a chain (the route path falls back to a full simulation for multi-event chains),
  and the MIP bound.
- 2026-10-16 **M2c done**: spatial and routes handle chains. `schedule_years` now returns **every**
  disturbance year per block (sorted), `green_up_violations` uses the closest pair of their years, and
  `spatial_penalty`/its callers (simulator, optimizer) follow. `Simulator.block_route_chain` routes a
  whole chain (with `block_route_accounts` delegating), `Optimizer._block_route_delta(block, chain)`
  prices it, the delta evaluator adds route cells to a block's contribution, and `delta_evaluator`
  now allows route accounts (no build, no duplicates, no edges). Verified: route+chain incremental vs
  full parity 0.000000 (95 multi-event chains). **Feasibility:** with rotations the softwood ceiling is
  **41.02 Mm3** (2.051 Mm3/period) versus 17.74 Mm3 one-pass, so the 1.3 Mm3/period x 20 = 26 Mm3
  target is **feasible** (63% of the ceiling); a 600-iteration SA already reaches 22.2 Mm3 with 1,991
  multi-rotation blocks. Remaining: the MIP bound's re-validation against rotations, and a longer
  even-flow run.
