# TSA46 500-block system-carbon trade-off

Date: 2026-10-28
Status: bounded search complete; exact replay recorded
Scope: 500-block TSA46 carbon subset, 50-year horizon, HWP lifecycle enabled

## Setup

- Dataset: `/tmp/opencode/tsa46-carbon-opt-dataset`
  - 500 blocks, 535 fragments, 6,272.27 ha
  - 109 package-compatible tracks; 29 CC treatments
- Package: `femic-carbon-46-346e66598638`, fingerprint `dac90e01…`
- HWP: public defaults (`df=1.0`) and high-displacement sensitivity (`df=2.4`)
- Initial schedule: 95 CC rows at offset 0
- Search: simulated annealing, seed 1, 50 iterations, 8 carbon base workers
- Exact verification: `ws4 carbon` with the same package/HWP config

The 500-block base now takes about 107 s with eight workers, so each search finishes in
roughly five minutes.

## Default HWP (df = 1.0)

Both objectives converged to the same schedule:

- 95 → 93 blocks
- dropped blocks 89 and 387
- moved block 24 from `CC@0` to `CC@30`

| Account | Max stock | Min emissions |
| --- | ---: | ---: |
| Offset-0 managed yield (m³) | 360,215.89 | 360,215.89 |
| Offset-49 system carbon (tC) | 2,028,044.63 | 2,028,044.63 |
| Offset-49 cumulative emissions (tCO2e) | 520,266.02 | 520,266.02 |
| Offset-49 HWP (tC) | 41,488.15 | 41,488.15 |

Neither carbon target was met:

- max-stock target 2,100,000 tC: short by 71,955.37 tC
- min-emissions target 500,000 tCO2e: over by 20,266.02 tCO2e

Exact replay differed by +18.25 tC on system carbon and +45.47 tCO2e on cumulative
emissions (about 9e-6 / 9e-5 relative). The schedule is identical, so the default
displacement factor does not create a stock/emissions conflict in this case.

## High displacement (df = 2.4)

The schedules now differ, but only slightly:

| Schedule | Blocks | Offset-0 yield (m³) | System C (tC) | Cumulative emissions (tCO2e) | HWP (tC) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Max stock | 93 | 360,215.89 | 2,028,044.63 | 223,576.76 | 41,488.15 |
| Min emissions | 95 | 372,417.64 | 2,024,021.54 | 230,572.49 | 42,070.77 |

The max-stock schedule is the same 93-block schedule as above; the min-emissions
schedule is the unchanged 95-block seed. The max-stock schedule therefore dominates on
both carbon accounts but gives up 12,201.75 m³ of managed yield. The min-emissions target
was already met at iteration 0; the search never improved it. The max-stock target is
still 71,955 tC short.

Exact replay:

- min-emissions: bit-identical to the ledger at offset 49.
- max-stock: -18.25 tC system carbon and -202.80 tCO2e cumulative emissions versus the
  ledger (0.0009% and 0.09% relative). The residual is the known cross-block aggregation
  difference when an event schedule is replayed in one batched SIT run.

## Forced min emissions (df = 2.4, cap 200,000 tCO2e)

A second min-emissions run used the high-displacement config and a cap well below the
seed's 230,572 tCO2e, with 100 iterations and the same 350k–390k m3 harvest band.

| Metric | Value |
| --- | ---: |
| Wall time | 432 s |
| Iterations | 100 |
| Yield | 360,215.89 m3 |
| System carbon | 2,028,044.63 tC |
| Cumulative emissions | 223,576.76 tCO2e |
| HWP | 41,488.15 tC |
| Emissions vs cap | +23,576.76 tCO2e |
| Exact cumulative emissions | 223,373.96 tCO2e |

The winning schedule is byte-identical to the max-stock 93-block schedule: blocks 89 and
387 removed, block 24 moved to `CC@30`. The search found it at iteration 4 and did not
improve over the next 96 iterations. The cap gap is therefore a search-quality result,
not evidence that 200k is unreachable.

Exact replay differed by +18.25 tC on system carbon, +202.80 tCO2e on cumulative
emissions, and -15.49 tC on HWP (all under 0.1%). The exact emissions are still above
the cap by 23,373.96 tCO2e.

## Multi-seed diagnostic (df = 2.4, cap 210,000 tCO2e)

The forced-cap run was repeated with three seeds, 200 iterations each, the same 95-block
initial schedule, and no `--seed-greedy`.

| Seed | Yield (m3) | System C (tC) | Emissions (tCO2e) | Exact emissions | HWP (tC) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 360,215.89 | 2,028,044.63 | 223,576.76 | 223,373.96 | 41,488.15 |
| 2 | 372,417.64 | 2,024,021.54 | 230,572.49 | 230,572.49 | 42,070.77 |
| 3 | 358,752.69 | 2,028,398.67 | 223,727.59 | 223,716.95 | 41,356.98 |

- All three runs used the full 200 iterations and finished in 10–12 minutes.
- All three missed the 210,000 cap by 13,374–20,572 tCO2e.
- Seed 1 gives the lowest exact emissions; seed 3 gives the highest exact system stock.
  The difference is small: ~343 tCO2e less emissions for ~373 tC less stock.
- The three schedules differ only in one to three CC rows; the plateau is reproducible.
- Ledger/exact differences: seed 2 is bit-identical; seeds 1 and 3 drift by up to
  ~203 tCO2e (0.09%) on cumulative emissions.

Within this 500-block subset and 200-iteration budget, **223–224k tCO2e is a stable
search plateau**, not a single-seed artifact. The 210k cap is not reached by any seed.

### `--seed-greedy` finding

The no-warm-start path with `--seed-greedy` did not complete. Floor-mode greedy seeding
is serial and prices every candidate chain through the carbon ledger: 3,093 chains at
~1.6 s each is ~85 minutes. The 25-minute `--time-limit` is checked only in the search
loop, so the run spent 60 minutes in seeding and executed zero iterations. This is a
separate engineering issue: seeding needs a deadline check and block-level parallelism
before it is a viable diagnostic path.

## Stand-state ledger reproduction (2026-10-29)

The 500-block high-displacement cases were rerun after the block-scoped ledger was
replaced by the stand-state cache. Results reproduce exactly:

| Case | Schedule SHA | Objective | System C | Exact system C | Emissions | Exact emissions |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Max stock | `5e66d423…` (unchanged) | 0.03426446 | 2,028,044.63 | 2,028,026.38 | 223,576.76 | 223,373.96 |
| Min emissions | `5112d187…` (unchanged) | 0.0 | 2,024,021.54 | 2,024,021.54 | 230,572.49 | 230,572.49 |

- Both schedules are byte-identical to the previously merged high-df schedules.
- Ledger accounts reproduce to ~1e-10.
- Exact replay reproduces the previous exact outputs.
- Runtime: max-stock 282 s, min-emissions 307 s.
- The max-stock ledger/exact gap is unchanged: +18.25 tC system, +202.80 tCO2e
  cumulative. It is a property of the offset-30 stand state, not the ledger refactor.

The corrected aspatial stand-state ledger is therefore validated against the old
block-scoped results and the exact batched engine.

## Reading

- At the public default displacement factor, this subset has no stock/emissions
  trade-off: reducing harvest improves both system carbon and emissions.
- At high displacement, max-stock and min-emissions converge to a narrow schedule
  frontier. The max-stock endpoint gives up ~12,200 m3 of managed yield versus the seed.
  The visible trade-off is carbon versus yield; stock and emissions move together.
- The 210k cap is not reached across three seeds. The repeated plateau at 223–224k is
  evidence for a near-frontier result within this search/search budget, not proof of
  infeasibility.
- The remaining blocker for a true no-warm-start diagnostic is greedy seeding, not the
  carbon ledger. Floor-mode seeding is serial, deadline-blind, and expensive.
- The exact engine remains the authority; ledger drift is under 0.1% on tested
  schedules.

## Artifacts

- `/tmp/opencode/tsa46-500-opt-max-stock{,-exact}/`
- `/tmp/opencode/tsa46-500-opt-min-emissions{,-exact}/`
- `/tmp/opencode/tsa46-500-highdf-opt-max-stock{,-exact}/`
- `/tmp/opencode/tsa46-500-highdf-opt-min-emissions{,-exact}/`
- `notes/reports/carbon-ledger-performance.md`
- `carbon-handoff/carbon-system-tradeoff-2026-10-28.md`
