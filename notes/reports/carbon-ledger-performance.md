# Carbon ledger: stand-state cache and area weighting

Date: 2026-10-29
Status: implemented and validated
Scope: WS4 carbon ledger used by the optimizer

## Problem

The ledger was block-scoped: it built SIT tables and ran libcbm once per block, then added
the blocks back together. On a 500-block TSA46 case that meant 500 repeated CBM runs for
the empty base and another full run per candidate chain in the seed. A no-warm-start seed
with 3,093 chains took 17 minutes; the actual carbon engine run over the whole 500-block
schedule takes about 35 seconds.

CBM is aspatial and linear in area. Repeating the same stand calculation for every block
that shares a track and age is the GCBM-style decomposition error, not a model requirement.

## Change

- `CarbonLedger` now prices a **stand state** once, keyed by
  `(track_id, age, treatment chain)`, and returns per-hectare accounts.
- A block is the area-weighted sum of its fragments' stand states.
- The 500-block TSA46 subset has 535 fragments but only **319 unique `(track, age)`
  states**; the empty base now prices 319 states, not 500 blocks.
- `CarbonLedger.prepare(candidates)` pre-prices every state a seed will score, so fork
  workers inherit the cache instead of recomputing identical states.
- Package tables are filtered to the tracks reachable from a state before SIT compile.
- `--carbon-workers` controls the fork workers used for the stand-state precompute.

## Measured effect

| Case | Before | After |
| --- | ---: | ---: |
| 500-block empty base, 8 workers | 107 s (500 block runs) | **58.5 s (319 state runs)** |
| 500-block capped seed + 20 iterations | 4m06s | **1m58s** |
| 500-block all-candidate seed | 17m17s | not used; capped |
| 10-block empty base | ~15 s | standalone state cache is cheaper |

Key base values match the old path to floating-point summation noise: offset-49 system
carbon is 2,270,724.615302 vs 2,270,724.6153, and cumulative emissions agree to ~3e-10
relative. The seed schedule and objective are unchanged.

## Remaining bottleneck

The ledger now runs CBM once per unique `(track, age, chain)` state, not once per block.
The remaining cost is the CBM spin-up and simulation per state. The next step is either a
batched stand-state compile or a track-level curve cache. The latter is plausible because
a continuous age-0 run exactly matches an age-A initialization for stocks; the only
difference is the initialization-year flux, which the ledger already normalizes to zero.

## Evidence

- `notes/reports/greedy-seeding-performance.md`
- `notes/reports/carbon-500block-tradeoff.md`
- `/tmp/opencode/tsa46-500-standstate-prep-smoke/`
- `/tmp/opencode/bench_standstate_ledger.out`
- `/tmp/opencode/cbm_initial_pool_test.out`
