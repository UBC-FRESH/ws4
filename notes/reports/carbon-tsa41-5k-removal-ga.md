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
| effect-table build (prepare + base + per-block rows, 64 workers) | **156 s** |
| GPU population search | **2.5 s** |
| exact replay / target report | ~28 s |

The table build is the cost; the search is effectively free once the rows exist. The
whole command, including exact replay, is **187 s** with 64 workers.

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

## State-cache adapter

`ws4 carbon-removal --state-cache PATH` now builds the carbon cells from a
`fresh-cbm` stand-state table instead of `CarbonLedger.prepare`. Non-carbon cells
still come from the WS4 simulator; the current chain must be empty or one `CC`
event present in the cache.

The adapter was checked against the exact ledger on a 20-state pilot cache with
offsets `-1, 0, 1, 2`:

- base values: max absolute difference **2.0e-11**
- block effects: max absolute difference **9.1e-13**

A 5k run using the partially built TSA41 cache:

- effect-table build: **0.0 s**
- MILP search: **4.1 s**
- total including exact replay: **50.6 s**
- same MILP genome: 1,597 removals, exact **5,694,966 tCO2e**

Without the state cache, the same 5k run was **207 s**. The full TSA41 cache
build is separate; see the `fresh-cbm` repository.

## Full TSA41 scale

The same command was run on the full TSA41 matrix, not just the 5k sample:

- Dataset: `tsa41-p120-matrix-full` — 148,828 blocks, 5,273 unique stand states
- Initial schedule: all 148,828 blocks at `CC@0`
- Target: yield floor 280M m3, minimize cumulative emissions
- 64 carbon workers, population 2,048, 3,000 generations, seed 1

| Metric | Baseline | Removal GA |
| --- | ---: | ---: |
| Blocks kept | 148,828 | **110,874** |
| Blocks removed | 0 | **37,954 (25.5%)** |
| Managed yield (m3) | 296,740,125 | **280,016,800** |
| Exact cumulative emissions @49 (tCO2e) | 368,283,052 | **213,103,705** |
| Reduction vs baseline | — | **42.14%** |
| System carbon @49 (tC) | — | **377,351,327** |
| HWP carbon @49 (tC) | — | **18,309,825** |

Costs: **976 s** table build, **78.6 s** population search, **1,217.7 s**
(20.3 min) total including exact replay. Exact target values:

- yield: 280,016,800.085 m3
- cumulative emissions: 213,103,705.410 tCO2e

The full-scale result is a keep/remove policy, not a full treatment schedule. It
shows that the exact effect-table path scales beyond the sample and remains
practical.

## Effect cache and exact solver

The effect table is now persisted under a content-addressed cache keyed by the
dataset tables, package fingerprint, schedule, targets, HWP config, and horizon.

- first 5k run: **207 s** (173 s table build, 3.8 s MILP, exact replay)
- repeat run with cache hit: **31.9 s**
- cache entries for the 5k case are on the order of the effect table itself
  (tens of KB), not the full libcbm state universe

`--solver auto` uses the binary MILP knapsack when the target set is one
minimum-cost target and one maximum-benefit target, and falls back to the
population otherwise. On the 5k effect table the MILP optimum is 5,785,622
incremental; the exact replay is 5,694,966 tCO2e. The GA schedule exact-replays at
5,692,533 tCO2e, slightly lower because exact whole-schedule SIT aggregation
differs from the additive effect table. Exact replay remains the reporting
authority.

## Full TSA41 state-cache run

The full 148,828-block TSA41 removal run was repeated with the partially built
state cache:

| Metric | Without state cache | With state cache |
| --- | ---: | ---: |
| Blocks | 148,828 | 148,828 |
| Removed | 37,954 | 37,954 |
| Yield (m3) | 280,016,800 | 280,016,800 |
| Exact emissions @49 (tCO2e) | 213,103,705 | 213,103,705 |
| Effect-table build | 976 s | **0.0 s** |
| Population search | 78.6 s | 79.9 s |
| Total including exact replay | 1,217.7 s | **1,069.5 s** |

The state-cache run was executed while the full cache builder was still using 64
workers, so the exact replay was contended. Even so, the table-build phase
disappeared and the schedule reproduced exactly. The remaining cost is the exact
replay, not carbon state construction.

## Production command

`ws4 carbon-removal` implements this path:

```bash
ws4 carbon-removal \
  --dataset /tmp/opencode/tsa41-5k-dataset \
  --package /srv/shared-data/gep/ws4/carbon-handoff/tsa41-p120-matrix-package \
  --schedule /tmp/opencode/tsa41-5k-cc-only.schedule.csv \
  --targets /tmp/opencode/tsa41-5k-targets-min-emissions.yaml \
  --years 50 --hwp-config config/carbon/hwp.bc.yaml \
  --workers 64 --population 2048 --generations 3000 --seed 1 \
  --out /tmp/opencode/tsa41-5k-carbon-removal-gpu2
```

The table build is parallel across exact stand states; the population runs on CUDA
when available. `--no-verify` skips the exact replay, but the reported result is
only authoritative with it.

## Artifacts

- `/tmp/opencode/tsa41-5k-removal-ga/schedule.csv`
- `/tmp/opencode/tsa41-5k-removal-ga/effects.npz`
- `/tmp/opencode/tsa41-5k-removal-ga-exact/`
- `/tmp/opencode/tsa41-5k-removal-ga-sim/`
