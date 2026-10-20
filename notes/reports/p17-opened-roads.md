# P17: roads dated to the period — and the reporting bug that hid the result

Routing now runs over the roads that exist in a period, opens a planned path when a block first needs
it, and charges the build once. The first comparison with the reference exposed a **reporting** defect
that had been attributed to routing: the period report was summing the annual distinct road lengths.
The corrected accounting puts WS4's road use *below* the reference's, and leaves maintenance as the
open discrepancy.

## The accounting bug

`RouteCostLedger.route_cost_report` folds years into the model's periods. It treated `LENGTH` as an
extensive column and summed the annual distinct lengths. With `period_width = 10`, a road used in nine
years counted nine times. The reference reports the **distinct road used at any time in the period**,
counted once; its period `LENGTH` is a segment-set quantity, not a sum of annual sets.

The corrected report unions the segment ids over the period and sums their lengths once.
`BUILTLENGTH` was already correct in effect (a road is built once), and the expenses and volume remain
sums. Two tests changed: `test_the_route_report_is_folded_into_the_models_periods` now asserts that a
route used in all ten years is 300 m, not 3,000.

## Period 1, `destination.MILL1`, 2026 sample

Ten years, `period_width = 10`, so this is the reference's period 1. The schedule's first treatment
period is 1, so WS4's years 1–9 carry wood; the reference's period covers years 1–10.

| quantity | reference | WS4 dated, corrected | ratio |
| --- | ---: | ---: | ---: |
| `LENGTH` (m) | 1,149,647 | **882,027** | **0.77** |
| `BUILTLENGTH` (m) | 732,073 | 386,352 | 0.53 |
| `BUILD_EXPENSE` | 3,660,367 | 1,931,761 | 0.53 |
| `HAUL_EXPENSE` | 11,174,512 | 6,294,644 | 0.56 |
| `MAINTAIN_EXPENSE` | 1,126,465 | 3,622,033 | **3.22** |
| `VOLUME` | 1,029,670 | 1,024,809 | 1.00 |

Before the fix the same run reported `LENGTH` 2,931,907 (2.55×) — the summed annual sets. The 2.55×
figure in the earlier version of this note was that artifact.

## What the road dating achieved

- A route uses an opened road rather than a shorter unopened one; the build is charged in the period the
  road opens; existing roads are not counted as built.
- The candidate-network test in the scenario export settles the availability question: the reference's
  own solution uses **22,901 of the sample's 24,273 zero-build segments** (union of
  `scenario/route_destination.MILL{1,2}.csv`: 31,612 segments, 8.8M m). Restricting WS4 to exactly that
  set changed `BUILTLENGTH`/`BUILD_EXPENSE` little and did not close the (then apparent) `LENGTH` gap —
  consistent with the gap being the aggregation, not the network.

## The remaining discrepancy: maintenance

WS4 charges maintenance once per used segment **per year**; the report sums the period's years. The
reference's period-1 maintenance (1,126,465) is almost exactly its period `LENGTH` (1,149,647), which is
what a **once-per-period** charge per metre looks like. WS4's figure is 3.22× the reference's while its
distinct road use is *lower*; the next task is to establish the reference's charging period and rate from
its own tables before changing the model. That is P17.5, re-scoped from "joint assignment" (the LENGTH
evidence no longer supports that hypothesis) to **the maintenance charge and the build/haul balance**.

## Files

- `tests/test_roads_opened.py` — six cases for opened roads, build-once, cache invalidation.
- `tmp/parity2025/run-dated2` — the corrected 10-year run (untracked).
- `tmp/parity2025/route-dated.yaml` — `initial_roads: existing`.

## Reproduce

```bash
cd tmp/parity2025
python - <<'PY'
from pathlib import Path
from ws4.sim.engine import Simulator
from ws4.roads.accounts import load_route_config
cfg = load_route_config(Path("route-dated.yaml"))
sim = Simulator.from_dataset(Path("c5_compiled"))
sim.run(Path("schedule-for-ws4.csv"), years=10, out_dir=Path("run-dated2"),
        route_model=cfg.model, route_accounts=cfg.route_accounts,
        duplicate_accounts=cfg.duplicate_accounts,
        product_allocations=cfg.product_allocations,
        period_width=cfg.period_width, maintenance=cfg.maintenance)
PY
```
