# TSA41 5,000-block, 200-iteration carbon search

Date: 2026-10-30
Status: bounded production sample complete; exact replay matches
Scope: TSA41 5k sample, CC-only schedule, public-default HWP, 50 years

## Setup

- Dataset: `/tmp/opencode/tsa41-5k-dataset`
  (5,000 blocks, 67,371.6 ha, 68 tracks, 1,748 unique `(track, age)` states)
- Package: `femic-carbon-41-0e5b491e6a34`
- HWP: `config/carbon/hwp.bc.yaml` (public defaults)
- Initial schedule: 5,000 `CC@0` events
- Targets: managed yield floor 9.5M m3; minimize cumulative system emissions
- Search: SA, seed 1, 200 iterations, LNS disabled (carbon CLI default)

## Result

| Metric | Baseline | 30 iterations | 200 iterations |
| --- | ---: | ---: | ---: |
| Scheduled blocks | 5,000 | 4,997 | **4,970** |
| Managed yield (m3) | 10,155,625 | 10,128,928 | **9,807,027** |
| Exact cumulative emissions @49 (tCO2e) | 12,816,648 | 12,801,867 | **12,460,557** |
| Reduction vs baseline | — | 14,782 (0.115%) | **356,091 (2.78%)** |
| System carbon @49 (tC) | — | 11,426,856 | **11,522,239** |
| HWP carbon @49 (tC) | — | 720,838 | **724,570** |

Wall time was **9m27s** for 200 iterations, including the initial and final
whole-schedule carbon runs. The 30-iteration run took 2m25s.

The extra 170 iterations reduced exact emissions by another **341,309 tCO2e
(2.66%)** while keeping the yield floor. The search removed 30 blocks and shifted
the remaining schedule; it did not merely cut area, because system carbon rose.

Exact replay:

- `ws4 carbon` offset-49 cumulative: **12,460,557.245 tCO2e**
- `account_values.csv` target: **12,460,557.245 tCO2e**
- no ledger/exact difference at the target cell

## Reading

- More iterations still buy meaningful carbon reductions on the 5k sample; the
  problem was search budget, not only model speed.
- The result is a local improvement from an all-CC start, not a carbon optimum.
- Exact `ws4 carbon` remains the reporting authority.

## Caveats

- 3.36% of TSA41 area, 68 of 70 tracks, 1,748 of 5,273 full-landscape states.
- CC-only; fire events are excluded because the simulator treats them as no-ops
  and they enlarge the incremental/exact gap.
- The yield floor is met with a 307k m3 margin; a stricter floor would trade away
  part of the emissions reduction.

## Artifacts

- `/tmp/opencode/tsa41-5k-opt-200/`
- `/tmp/opencode/tsa41-5k-opt-200-exact/`
