# Carbon ledger performance: package and per-block SIT filtering

Date: 2026-10-28
Status: implemented and validated
Scope: WS4 block-level carbon ledger used by the optimizer

## Problem

A 500-block TSA46 system-carbon search spent **3 h 47 min before iteration 1**.
`CarbonLedger.base_values()` rebuilt SIT tables from the full FEMIC package for each
block. `_boundary_classifiers` and `_build_yield` were the dominant costs, because the
package carried 10,664 track names even though a block reaches only a few.

## Change

- Added `filter_carbon_package(package, track_names)` in `ws4/carbon/package.py`.
  It keeps the manifest, hashes, and fingerprint, but restricts the track-scoped tables
  (`track_carbon_map`, `inventory`, `yield`, `curve_carbon_map`) to named tracks.
- The ledger first filters the package and treatments to the tracks reachable from the
  dataset, then builds a cached per-block context containing only that block's reachable
  source and destination tracks.
- `_run()` now compiles SIT from the block context. Repeated chains reuse the context;
  no package-wide yield or boundary scan is repeated per block.
- `CarbonLedger(base_workers=n)` / `ws4 optimize --carbon-workers n` computes the
  empty-schedule base in fork workers. The optimizer forces one worker when `islands` or
  process-parallel `starts` are active, to avoid nested pools.

## Measured effect

| Case | Before | After |
| --- | ---: | ---: |
| 500-block empty base, serial | 3 h 47 min before iteration 1 | **699 s (~12 min)** |
| 500-block empty base, 8 workers | n/a | **107 s** (bit-identical values) |
| 10-block empty base | ~3.7 min (estimated) | **14.9 s** |
| 500-block 20-iteration search | did not start | **870 s total, 20 iterations completed** |

The 500-block search used the 10,664-track TSA46 package and 500-block dataset. It ran
20 iterations in 14m30s and improved the incumbent objective from 0.108407 to
0.106873. Exact `ws4 carbon` replay differed from the ledger by ~9e-6 relative on
`carbon.system.total`; no-harvest base values agreed to ~1e-8. The residual comes from
cross-block aggregation in the exact SIT run, not from the package filter.

## Remaining bottleneck

The remaining cost is one libcbm run per block. Eight workers make the 500-block base
about two minutes, which is usable for a long search; a batched base (for example a block
classifier in the SIT inventory, or a precomputed per-track/age unit curve) is still the
next step for interactive use.

## Evidence

- `/tmp/opencode/tsa46-500block-opt-max-stock-fixed/summary.json`
- `/tmp/opencode/tsa46-500block-opt-max-stock-fixed/telemetry.jsonl`
- `/tmp/opencode/tsa46-500block-verify-fixed/carbon_accounts.csv`
- `/tmp/opencode/tsa46-carbon-system-tradeoff-2026-10-28.md` (workspace handoff)
