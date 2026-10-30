# TSA41 5k exact effect table and removal GA

Date: 2026-10-30
Status: bounded experiment complete; exact replay recorded
Scope: TSA41 5k sample, current `CC@0` keep/remove decision, public-default HWP

## Why this experiment

The 500-iteration simulated annealer reaches 4.50% below the baseline. Its moves
are local: one block at a time, with a 9.5M m3 yield floor. A global keep/remove
decision is additive, so it can be priced exactly once and searched as a genome.

This follows the P83 GPU population-search structure: build exact effect rows, then
evaluate a population on the device. For carbon the table is small because the
candidate set is restricted to the current chain and untreated.

## Setup

- Dataset: `/tmp/opencode/tsa41-5k-dataset`
  (5,000 blocks, 67,371.6 ha, 68 tracks, 1,748 unique stand states)
- Package: `femic-carbon-41-0e5b491e6a34`
- HWP: `config/carbon/hwp.bc.yaml`
- Initial schedule: 5,000 `CC@0` events
- Genome: one bit per block; 1 keeps the current chain, 0 leaves the block untreated
- Targets: managed yield floor 9.5M m3; minimize cumulative system emissions
- GPU: RTX PRO 6000 Blackwell Max-Q; PyTorch 2.14.1+cu130

## Exact effect table

For every block, the experiment prices the current-chain delta against untreated for
two cells:

- `product.Yield.managed.Total` at offset 0
- `carbon.co2e.system.emissions.cumulative` at offset 49

Costs:

| Step | Wall |
| --- | ---: |
| `CarbonLedger.prepare` for 5,000 current chains | **444 s** |
| empty base values | 19 s |
| 5,000 per-block effects | 15 s |
| GPU population search | **2.3 s** |
| exact `ws4 carbon` replay | 63 s |

The table build is the cost; the search is effectively free once the rows exist.

## Result

| Metric | Baseline | 500-iteration SA | Removal GA |
| --- | ---: | ---: | ---: |
| Scheduled blocks | 5,000 | 4,934 | **3,396** |
| Removed blocks | 0 | 66 | **1,604** |
| Managed yield (m3) | 10,155,625 | 9,500,401 | **9,500,005** |
| Exact cumulative emissions @49 (tCO2e) | 12,816,648 | 12,240,329 | **5,692,533** |
| Reduction vs baseline | — | 4.50% | **55.58%** |
| System carbon @49 (tC) | 10,399,340 | 11,578,794 | **13,537,673** |
| HWP carbon @49 (tC) | 720,386 | 732,344 | **597,348** |

The genome removes 32% of the blocks while meeting the yield floor within 5 m3.
Exact replay:

- `ws4 carbon` offset-49 cumulative: **5,692,532.565 tCO2e**
- exact yield: **9,500,004.642 m3**
- system carbon: **13,537,673.073 tC**
- HWP carbon: **597,348.350 tC**

The incremental effect-table prediction was 5,785,696 tCO2e; exact replay is
**1.6% lower**. That difference is the same event-aggregation difference seen
between the incremental stand-state sum and the whole-schedule SIT run; the exact
run is the reported value.

## Reading

- The large gain comes from **global removal decisions**, not from a better
  single-block local search. The 500-iteration SA was trapped near the all-in
  schedule because moving one block at a time barely changes the yield floor.
- The effect table is exact and reusable for this restricted decision space. GPU
  evaluation is not the bottleneck at this size; `CarbonLedger.prepare` is.
- This is a real WS4 carbon result on the 5k sample, but the decision space is
  deliberately narrow: keep or remove the current `CC@0` chain, no shifts, no
  multiple events.

## Caveats

- 3.36% of TSA41 area, 68 of 70 tracks, 1,748 of 5,273 full-landscape states.
- Removal-only; shifted CC years, fertilization, and multi-event chains are out of
  scope.
- The exact schedule is at the yield floor; small rounding or model changes can
  violate it.
- Exact `ws4 carbon` remains the authority.

## Artifacts

- `/tmp/opencode/tsa41-5k-removal-ga/schedule.csv`
- `/tmp/opencode/tsa41-5k-removal-ga/effects.npz`
- `/tmp/opencode/tsa41-5k-removal-ga-exact/`
- `/tmp/opencode/tsa41-5k-removal-ga-sim/`
