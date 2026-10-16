# Faster route-record accumulation (performance spike)

Status: **spike**. Branch `spike/route-record`, off P6 head `84c34f4`. Checkpoint tag
`p6-routerecord-checkpoint` for one-command rollback.

Related: `notes/design/ws4-incremental-route-accounts.md`, `notes/performance.md`.

## 1. Motivation and evidence

`RouteCostLedger.record` in reporting mode (`collect=True`) is 0.78 s of a 3-year, 300-block C5 run
(1.18 s cumulative). cProfile: 949 530 `_SegmentState` instantiations and 969 256 `dict.setdefault`
calls — the per-record loop over a route's segments, once per produced product. This is a **one-time
reporting** cost (the optimizer uses `collect=False`).

## 2. Hypothesis

Products that route from the same block to the same destination share the **same route**, so their
per-segment contributions can be aggregated:

- volume per segment is the sum of the products' volumes (additive);
- haul per segment is `volume * haul_rate` (linear in volume);
- maintenance is charged per record, so it is `maintain_cost * (number of records)` on the route;
- build is charged once per segment across the run.

Aggregating by `(year, destination, route)` and doing one segment pass per route cuts segment visits
from `products x segments` to `routes x segments` (~9x on C5).

## 3. Design

- `record` (collect=True): append the route row (for `route_values.csv`), update the per-destination
  summary totals (volume/haul/maintain), and add `(volume, count)` to a `_flows` dict keyed by
  `(year, destination, route.segment_ids)`. No per-segment work here.
- `_flush`: iterate `_flows` in insertion order and do the per-segment accumulation **once per route**
  (volume, haul = `volume * haul_rate`, maintain = `maintain_cost * count`, build once). Insertion order
  preserves the current build attribution (the first record that used the segment).
- Call `_flush` at the start of `network_table`, `route_table`, `route_cost_report`, `route_rows`,
  `account_values`, and `write`, so the outputs are unchanged.
- `collect=False` (the optimizer's path) is untouched.

## 4. Correctness plan

- The aggregation is exact (volume additive, haul linear, maintenance per record, build once), so the
  outputs must be byte-identical to the current per-record loop.
- Cross-check: `account_values` from a `collect=True` ledger must equal `account_values` from a
  `collect=False` ledger for the same schedule (two independent aggregations of the same flows).
- Internal consistency: the network table's per-segment volume sums to the total routed volume;
  `route_cost_report` totals match the per-destination summary.
- The existing suite is the gate.

## 5. Targets

| Metric | Before | Target |
| --- | ---: | ---: |
| `record`, 3-year, 300-block C5 run (collect=True) | 0.78 s | < 0.2 s |

## 6. Risks

| Risk | Mitigation |
| --- | --- |
| Flush ordering changes build attribution | Iterate `_flows` in insertion order; cross-check test |
| An output reads before flush | `_flush` is called by every reader |
| Maintenance count wrong | `count` is incremented per volume>0 record, matching the current loop |

## 7. Milestones

- **M1** implement `_flows` + `_flush`; cross-check and consistency tests; full suite green.
- **M2** A/B vs `p6-routerecord-checkpoint`; docs and decision.

## 8. Decision and rollback

- **Adopt** if `record` drops below 0.2 s with identical outputs.
- **Abandon** otherwise: `git checkout feature/p6-performance`.

## 9. Log

- 2026-10-16: plan written; profiling done (section 1). Starting M1.
