# Incremental route evaluation: profile and design

Status: P45.1 design note. No incremental code lands here.

## Why

The optimizer evaluates the whole schedule for a route configuration when any route
account is per-segment (`build`, `maintain`) or a delivery target is present. The
per-block route delta in `ws4/opt/engine.py` covers only additive haul and volume
accounts. On c5 the full path is the remaining hot spot.

## Profile

Command:

```bash
python scripts/profile_route.py \
  --dataset runtime/c5_compiled \
  --targets config/targets.yaml \
  --route-config config/route.yaml \
  --schedule runtime/runs/web-.../schedule.csv \
  --years 50 --repeats 2 --out route-profile.json
```

c5, 32 scheduled blocks, four route accounts:

| Measure | Value |
| --- | ---: |
| Full evaluation | 0.451 s/evaluation |
| `simulate` cumulative | 0.407 s/evaluation |
| `account_values` | 0.236 s/evaluation |
| `apply_treatments` | 0.139 s/evaluation |
| curve gather | 0.139 s/evaluation |

The cost is the full simulator and its account ledger, not route assignment: the route
model already caches the exclusive destination per `(block, product)`.

## What can be incremental

The route ledger is a function of block route events:

```text
(year, destination, product, volume, segment_ids, length_m, haul_cost)
```

For a fixed treatment chain, a block's events are deterministic and independent of the
rest of the schedule, except for delivery targets and the road-opening rule.

A `RouteAggregate` can therefore keep:

- `events[block][chain]`: the block's cached route events.
- `traffic[(year, segment)]`: total volume on a segment.
- `dest_volume[(year, destination)]`, `dest_haul[(year, destination)]`.
- `segment_years[segment]`: the years a segment is used.
- `first_use[segment]`: the earliest year, which determines the build charge.
- `build_charged`: the set of segments already charged.

A move subtracts the old block's events and adds the new block's events. Only touched
segments and destinations need recomputation.

## What must stay full

- **Delivery targets**: they allocate a whole year's volume across blocks, so a block is
  not independent.
- **Planned-network opening**: the first block that uses a planned path opens it, and
  later blocks route over the opened set. A move can change which block opens which
  segments.
- **Any route account outside haul, volume, build, and maintain**, until it has an
  explicit incremental rule.

These cases fall back to `_full_values`; the search and the final report must use the
same path.

## Invariants

1. A segment's build cost is charged once, in its first used year, and never again.
2. Maintenance is charged per segment per period from the period's traffic, using the
   configured `MaintenanceCharge`.
3. Haul and volume are additive over blocks and destinations.
4. The exclusive destination per `(block, product)` is unchanged.
5. Removing a block removes exactly its events; re-adding it restores the same totals.
6. The aggregate is independent of block insertion order.
7. Duplicate and meta accounts resolve after the aggregate, as they do now.

## Parity tests for P46

- Random schedule: full and aggregate values agree for every `(year, account)` cell.
- Build: two blocks over the same segment charge build once; removing one keeps it.
- Maintenance: traffic and per-period maintenance match the full ledger.
- Delivery fallback: an incremental request falls back and matches full.
- Repeated removal/re-add: totals return to the same values.
- Empty schedule and one-block schedule.
- GBR and c5 production route configs.

## Decision

Proceed to P46 only if the parity suite passes. The target is a measured speedup on c5
and a GBR subset; no change to route semantics or report values is acceptable.

## P46 outcome

P46 implemented the safe first slice: cached per-block route events replayed in the
full simulation's order. It removes the simulator from the route path for a fully open
network with no delivery target, while the ledger still performs the exact build-once
and per-period maintenance accounting. Delivery, opened-road growth, and unsupported
accounts remain on the full path. Segment-level subtraction was not implemented; the
warm cache is the measured win.
