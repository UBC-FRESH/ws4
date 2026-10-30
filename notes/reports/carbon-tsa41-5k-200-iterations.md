# TSA41 5,000-block, 200- and 500-iteration carbon search

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
- Search: SA, seed 1, 200 / 500 iterations, LNS disabled (carbon CLI default)

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

## 500-iteration follow-up

The same setup was rerun for 500 iterations:

| Metric | 200 iterations | 500 iterations |
| --- | ---: | ---: |
| Scheduled blocks | 4,970 | **4,934** |
| Managed yield (m3) | 9,807,027 | **9,500,401** |
| Exact cumulative emissions @49 (tCO2e) | 12,460,557 | **12,240,329** |
| Reduction vs baseline | 356,091 (2.78%) | **576,319 (4.50%)** |
| System carbon @49 (tC) | 11,522,239 | **11,578,794** |
| HWP carbon @49 (tC) | 724,570 | **732,344** |

Wall time was **19m37s**. The extra 300 iterations bought another **220,228
tCO2e (1.76%)** and the yield floor is still met, but only by 401 m3; this run is
at the floor, not inside it. Exact replay matches the target cell:
**12,240,329.178 tCO2e**.

## Yield-floor sensitivity

The same 200-iteration search was rerun with stricter floors:

| Yield floor (m3) | Realized yield (m3) | Exact emissions @49 (tCO2e) | Reduction vs baseline |
| ---: | ---: | ---: | ---: |
| 9,500,000 | 9,807,027 | 12,460,557 | 356,091 (2.78%) |
| 9,800,000 | 9,807,027 | 12,460,557 | 356,091 (2.78%) |
| 10,000,000 | 10,000,084 | 12,743,634 | 73,014 (0.57%) |

The 9.8M floor is non-binding: the 9.5M run already lands at 9.807M. Moving
to a 10.0M floor gives back **283,077 tCO2e** of the reduction, or about
0.68% of baseline emissions. The frontier is therefore steep near the
baseline yield, not a smooth small trade-off.

Exact replay of the 10.0M schedule matches its reported target:
**12,743,634.203 tCO2e**.

## Reading

- More iterations still buy meaningful carbon reductions on the 5k sample: 500
  iterations reach 4.50% below baseline, versus 2.78% at 200. Search budget, not
  model runtime, is now the main limit.
- The result is a local improvement from an all-CC start, not a carbon optimum.
- Exact `ws4 carbon` remains the reporting authority.

## Caveats

- 3.36% of TSA41 area, 68 of 70 tracks, 1,748 of 5,273 full-landscape states.
- CC-only; fire events are excluded because the simulator treats them as no-ops
  and they enlarge the incremental/exact gap.
- The 200-iteration run meets the 9.5M yield floor with a 307k m3 margin; the
  500-iteration run sits at 9.5004M. A 10.0M floor gives back about 283k tCO2e of
  the 200-iteration reduction.

## Artifacts

- `/tmp/opencode/tsa41-5k-opt-200/`
- `/tmp/opencode/tsa41-5k-opt-200-exact/`
- `/tmp/opencode/tsa41-5k-opt-200-y98/`
- `/tmp/opencode/tsa41-5k-opt-200-y100/`
- `/tmp/opencode/tsa41-5k-opt-200-y100-exact/`
- `/tmp/opencode/tsa41-5k-opt-500/`
- `/tmp/opencode/tsa41-5k-opt-500-exact/`
