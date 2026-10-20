# P17 first measurement: opened roads change the build, not yet the length

The mechanism is in: a network can start from the roads that exist (zero build cost), route only over
opened segments, and open a planned path when a block first needs it. On the 2026 sample, 10 years with
`period_width = 10` (so the table below is the reference's period 1), `destination.MILL1`:

| quantity | reference | WS4 planned (before) | WS4 dated (after) | after / reference |
| --- | ---: | ---: | ---: | ---: |
| `LENGTH` (m) | 1,149,647 | 3,071,421 | 2,931,907 | **2.55** |
| `BUILTLENGTH` (m) | 732,073 | 730,679 | 386,352 | **0.53** |
| `BUILD_EXPENSE` | 3,660,367 | 2,022,647 | 1,931,761 | **0.53** |
| `HAUL_EXPENSE` | 11,174,512 | 6,266,806 | 6,294,644 | **0.56** |
| `MAINTAIN_EXPENSE` | 1,126,465 | 3,516,625 | 3,622,033 | **3.22** |
| `VOLUME` | 1,029,670 | 1,042,261 | — | ≈1.01 |

The planned run is `tmp/parity2025/run-period`; the dated run is `tmp/parity2025/run-dated`, built from
`route-dated.yaml` (`initial_roads: existing`). Both use the same schedule and eligibility.

## What the change achieved

- The build is charged in the period the road opens, and an existing road is not counted as built: the
  per-period build expense falls from 2.02M to 1.93M and the built length from 731k to 386k.
- A route now prefers an opened road to a shorter unopened one, and the cache is invalidated when the
  network grows (`tests/test_roads_opened.py`).

## What it did not achieve

`LENGTH` is still **2.55×** the reference. Dating the roads moved it only 4.5%. The reason is the
**choice of roads**, not their availability:

- The existing set is dense — 24,273 zero-build-cost segments, 4.42M m inside the connected network. A
  least-haul router uses 2.9M m of it in period 1.
- The reference reports 1.15M m of road in use, of which 732k is built in that period; its solve uses a
  **compact** network, not every existing spur. Its haul expense is 1.8× WS4's, so it is trading haul
  for road.
- WS4's router prices haul only. With no road target in the objective it takes the cheapest haul path
  regardless of how much road that opens — which is what the reference does *when no road target is
  active*, but over a network it has built, not over the full existing GIS network.

## The next lever, named

Matching `LENGTH` needs one of:

1. **A road-aware route choice** — price the build of a new segment in the path (and, when a road
   target is active, the maintenance/disturbance it implies), which is the reference's trade-off.
2. **An initial-set fit** — determine which zero-build-cost segments the reference's model actually
   starts with. The sample's `BUILD = 0` set (4.42M m) is far larger than the 1.15M m the reference uses
   in period 1, so either its model's road table is a subset or its solve deliberately uses a subset.

The second is a data question and can be tested from the export; the first is a modelling change with a
measurable trade-off. Neither is asserted here; the measurement says where the gap lives.

## Reproduce

```bash
cd tmp/parity2025
# route-dated.yaml is route.yaml with "initial_roads: existing"
python - <<'PY'
from pathlib import Path
from ws4.sim.engine import Simulator
from ws4.roads.accounts import load_route_config
cfg = load_route_config(Path("route-dated.yaml"))
sim = Simulator.from_dataset(Path("c5_compiled"))
sim.run(Path("schedule-for-ws4.csv"), years=10, out_dir=Path("run-dated"),
        route_model=cfg.model, route_accounts=cfg.route_accounts,
        duplicate_accounts=cfg.duplicate_accounts,
        product_allocations=cfg.product_allocations,
        period_width=cfg.period_width, maintenance=cfg.maintenance)
PY
```

## The reference's own solution road set

The scenario export carries the road set of the reference's solution in
`scenarios/base/scenario/route_destination.MILL{1,2}.csv.gz` (`SEGMENT,FNODE,TNODE,FIXED`):

| | segments | length (m) | zero-build segments | planned segments |
| --- | ---: | ---: | ---: | ---: |
| MILL 1 | 26,905 | 6,585,444 | 20,934 (3,615,205 m) | 5,971 (2,970,239 m) |
| MILL 2 | 26,905 | 6,624,381 | 20,949 (3,626,217 m) | 5,956 (2,998,163 m) |
| union | 31,612 | 8,802,088 | 22,901 | 8,711 (4,697,015 m) |

All rows carry `FIXED = false`.

This settles one of the two levers: **the initial set is not the gap.** The solution's existing-road
set is 22,901 of the sample's 24,273 zero-build-cost segments (94%), so starting from the zero-build
set is close to the reference's own available network. What differs is the **per-period selection**:
the reference's `LENGTH` (1.15M in period 1) is a subset of this 6.6M m set, while WS4's independent
least-haul paths use 2.9M in the same period.

The plausible cause is the **coupling of assignments**. The reference solves block-to-mill assignment
jointly, so blocks share the road they use; WS4 chooses each block's least-haul route independently,
and independent shortest paths fan out over parallel roads. The next test is a joint assignment
(min-cost flow, or a shared-path heuristic) against the current independent routing, with `LENGTH`
and haul as the two quantities — not another initial-set variant.
