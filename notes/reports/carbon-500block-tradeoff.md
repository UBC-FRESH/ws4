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

## Reading

- At the public default displacement factor, this subset has no stock/emissions
  trade-off: reducing harvest improves both system carbon and emissions.
- At high displacement, a small schedule difference appears, but the search is mostly
  staying at the seed. The 50-iteration SA moved only three blocks.
- Both carbon targets are aggressive relative to the feasible schedule; the search
  result is a bounded mechanism result, not a policy optimum.
- The exact engine remains the authority; the ledger is within 0.09% on the tested
  schedules.

## Artifacts

- `/tmp/opencode/tsa46-500-opt-max-stock{,-exact}/`
- `/tmp/opencode/tsa46-500-opt-min-emissions{,-exact}/`
- `/tmp/opencode/tsa46-500-highdf-opt-max-stock{,-exact}/`
- `/tmp/opencode/tsa46-500-highdf-opt-min-emissions{,-exact}/`
- `notes/reports/carbon-ledger-performance.md`
- `carbon-handoff/carbon-system-tradeoff-2026-10-28.md`
