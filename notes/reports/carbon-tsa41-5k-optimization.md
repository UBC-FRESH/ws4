# TSA41 5,000-block carbon search and whole-schedule evaluation

Date: 2026-10-30
Status: bounded optimization complete; search cost fixed
Scope: TSA41 5k sample, CC-only schedule, public-default HWP

## Findings

Two independent costs made the carbon search look slower than the model:

1. The initial schedule was evaluated stand state by stand state. The ledger now runs
   **one whole-schedule libcbm model** for the initial carbon totals: all fragments are
   in the inventory, only scheduled blocks carry events, and the fixed model cost is
   paid once. Incremental moves still price only the blocks they touch.
2. The default LNS operator is a poor fit for carbon. A bulk move creates many new
   stand-state evaluations. Disabling LNS made both the 500-block and 5k searches
   faster and at least as good. The CLI now defaults `lns_weight` to `0` when
   `--carbon-package` is present; pass `--lns-weight` explicitly to re-enable it.

The whole-schedule path also changes the target report: `report_targets.csv` now reads
the exact batch value, not the sum of incremental contributions. Exact `ws4 carbon`
replay agrees with that batch value.

## TSA41 500-block

| Run | Wall | Iterations | Search objective | Exact emissions @49 |
| --- | ---: | ---: | ---: | ---: |
| original per-state initial evaluation | 8m37s | 30 | 1270.30 | 1,258,901 |
| per-state precompute + no LNS | 1m50s | 30 | 1268.71 | not replayed |
| whole-schedule batch + no LNS | **1m40s** | 30 | 1268.71 | **1,263,223** |

Baseline exact emissions are 1,281,211 tCO2e. The batch run is a 17,988 tCO2e
(1.40%) reduction, with system carbon at 1,141,071 tC (baseline 1,136,807) and HWP at
72,676 tC (baseline 71,815). Managed yield is 432,756 m3 against the 430k floor.

## TSA41 5,000-block

- Dataset: 5,000 blocks, 67,371.6 ha, 68 tracks, **1,748 unique `(track, age)` states**
- Schedule: CC-only; 5,000 blocks
- Targets: managed yield floor 9.5M m3; minimize cumulative emissions
- Setup: 8 carbon workers, seed 1

| Run | Wall | Iterations | Search objective | Exact emissions @49 |
| --- | ---: | ---: | ---: | ---: |
| per-state precompute, LNS enabled | 24m57s | 14 | 12,803.59 | not used |
| per-state precompute, no LNS | 8m07s | 30 | 12,802.43 | 12,801,867 |
| whole-schedule batch, no LNS | **2m25s** | 30 | **12,801.85** | **12,801,867** |

Baseline exact cumulative emissions: **12,816,648 tCO2e**. The batch run reduces exact
emissions by **14,782 tCO2e (0.115%)** while holding more total system carbon. Managed
yield is 10,128,928 m3, above the 9.5M floor. The incremental objective differs from
the exact replay by 21 tCO2e (0.0002%).

A 200-iteration follow-up reaches **12,460,557 tCO2e** (-2.78% vs baseline); see
`reports/carbon-tsa41-5k-200-iterations.md`.

## Caveats

- The 5k sample is 3.36% of TSA41 area, 68 of 70 tracks, and 1,748 of 5,273 full-landscape
  states. It is a production-scale regression sample, not a full-TSA optimum.
- The emissions ceiling is not reachable from an all-CC start; the run is a local
  improvement, not a carbon-optimal schedule.
- The 5k result uses CC-only; fire events are excluded because the simulator treats them
  as no-ops and they inflated the incremental/exact gap.
- Exact `ws4 carbon` remains the reporting authority.

## Artifacts

- `/tmp/opencode/tsa41-5k-opt-batch31/`
- `/tmp/opencode/tsa41-5k-opt-batch31-exact/`
- `/tmp/opencode/tsa41-500-opt-batch31/`
- `/tmp/opencode/tsa41-500-opt-batch31-exact/`
