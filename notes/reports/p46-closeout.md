# Phase close-out report: P46 Cached route event ledger

Phase: P46, Cached route event ledger
Parent issue: #382
Pull request: #386
Status: merged and closed on 2026-10-26 as `6c31d49`.
Date: 2026-10-25

## Recommendation

1. Squash-merge the P46 pull request and delete `feature/p46-route-events`.
2. Close tasks #383/#384/#385 and parent #382.
3. Accept the GBR benchmark deviation below, or keep P46.3 open until a production GBR
   route configuration exists.

Settings changes: none.

## Acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Incremental and full route values agree on fixtures and c5. | Every `(year, account)` cell agrees within `1.9e-8` on c5; fixture tests cover build, maintain, haul, volume, both orders. | Met |
| Shared-segment build is charged once and attributed correctly. | Fixture has two blocks on one segment; `route.build` totals 5.0 and parity is exact. | Met |
| Delivery and opened-road configurations keep the full path. | `test_delivery_and_opened_roads_keep_the_full_route_path`; `_route_event_values` returns None for both. | Met |
| A repeatable benchmark reports cold and warm times. | `scripts/benchmark_route_events.py`; c5 JSON below. | Met |
| Dashboard green. | Green at the report commit. | Met |

## c5 benchmark

Schedule: `web-20261024-221127-1`, 32 blocks, 64 routed events, 50 years, four route
accounts (two haul, build, maintenance).

| Measure | Seconds |
| --- | ---: |
| Full simulation | 0.303 |
| Cached, cold event cache | 1.789 |
| Cached, warm event cache | 0.037 |
| Warm speedup | 8.25x |

Cold is slower because the first evaluation generates every block's events; a search
pays that once and then uses the cache. The largest value difference is `1.86e-8`.

## Deviations

- **No GBR route benchmark.** The GBR instances in this workspace have compiled matrices
  and targets but no road segments or route configuration, so a GBR route benchmark would
  require inventing a network. I did not do that. c5 is the only real production route
  model available here. P46.3's GBR half is therefore not evidenced; accept the deviation
  or leave the task open until a GBR route config is supplied.
- Segment-level subtract/add was not implemented. The measured warm path caches events
  and replays one ledger; that is exact and 8.25x faster on c5.
- The cold cache is deliberately reported rather than hidden; it is slower than full.
