# P120 multi-boundary carbon: production evidence

Date: 2026-10-27
Status: delivered and validated; no open carbon PRs
Scope: FEMIC package producer + WS4 consumer, TSA08/16/40/41 and TSA46 regression

This report consolidates the production evidence that used to live only in the
workspace handoff. It is the durable repository record for the split-TSA work.

## Merged code

- FEMIC #417, #421, #422
- WS4 #455, #460
- WS4 #498 (inventory-row aggregation) and #515 (event aggregation)

## Production packages

| TSA | Package id | Tracks | Area (ha) | Yield rows | Eco-boundary split (ha) |
| --- | --- | ---: | ---: | ---: | --- |
| TSA08 | `femic-carbon-08-6c14f038985f` | 33 | 4,341,402.9 | 1,023 | Taiga Plains 2,858,562; Boreal Cordillera 1,482,579; Boreal Plains 261 |
| TSA16 | `femic-carbon-16-c92d20527b46` | 49 | 2,807,096.4 | 1,519 | Boreal Cordillera 1,219,269; Montane Cordillera 1,587,827 |
| TSA40 | `femic-carbon-40-d49e9e05b9b9` | 30 | 2,497,704.2 | 930 | Boreal Cordillera 156,217; Boreal Plains 1,347,095; Montane Cordillera 211,027; Taiga Plains 783,366 |
| TSA41 | `femic-carbon-41-5ee703516c93` | 38 | 1,954,327.1 | 1,178 | Boreal Plains 917,139; Montane Cordillera 1,037,189 |

All four packages validate with CBM defaults `1.2.9300.391` and SHA-256
`4bd722d8825abeda3c9cf77247bbd4903824259e2fcc046d9a335336c8842155`. The WS4
500-row production runs completed without `--allow-defaults-mismatch`.

## Compiled matrices and full schedules

| TSA | Matrix blocks | Matrix area (ha) | SIT rows | Full 50-year result (tC) | Runtime |
| --- | ---: | ---: | ---: | --- | ---: |
| TSA08 | 500 | 11,286.7 | 1,078 | 1,109,079,716.4 -> 844,189,238.1 | 641 s |
| TSA16 | 500 | 7,529.7 | 986 | 644,947,571.8 -> 404,510,934.2 | 552 s |
| TSA40 | 500 | 4,765.3 | 1,877 | 584,367,066.8 -> 379,138,290.3 | 738 s |
| TSA41 | 500 | 6,587.0 | 979 | 461,008,030.0 -> 282,497,147.0 | 358 s |

The full schedules use CC at offset 0 and fire at offsets 20 and 40 on every block.
The TSA08 schedule contains 371,565 blocks and 1,114,695 events. Event aggregation
reduced a 10,000-block TSA08 schedule from 1,124 s to 206 s; the full schedule now
runs in 641 s.

Full-landscape empty-schedule baselines (one step) are:

| TSA | Area (ha) | Aggregated SIT rows | Start -> end (tC) | Runtime |
| --- | ---: | ---: | --- | ---: |
| TSA08 | 4,341,402.9 | 7,931 | 1,109,079,716.4 -> 1,111,346,446.0 | 105.8 s |
| TSA16 | 2,807,096.4 | 15,061 | 644,947,571.8 -> 646,535,130.6 | 87.0 s |
| TSA40 | 2,497,704.2 | 15,193 | 584,367,066.8 -> 586,626,274.5 | 107.3 s |
| TSA41 | 1,954,327.1 | 10,098 | 461,008,030.0 -> 462,579,543.1 | 60.0 s |

The same inventory aggregation reduced the full-landscape one-step time from more
than 20 minutes to 60-107 s.

## TSA46 regression

- 500 blocks / 535 fragments / 6,272.3 ha.
- 95 managed CC events at offset 0 and two fire events per block at offsets 20 and 40:
  1,095 events, 50 steps.
- SIT inventory 860 rows split 367.6 ha Montane / 5,904.7 ha Pacific.
- Carbon: 2,227,732.0 -> 1,180,006.3 tC.

## GCBM bridge

A 500-block TSA46 coarse project was exported and run through the FEMIC walltowall
bridge. Earlier same-footprint work recorded WS4 area 6,272.27 ha versus GCBM
inventory area 6,269.41 ha (0.05% difference) and a clean project validation. The
bridge is a format/readiness check. It is not a parity test: GCBM and libcbm are
separate CFS CBM implementations, and WS4 does not target numerical equality.

## Caveats

- A full-schedule SIT event is allocated by classifier set and area, not by block id.
  When several blocks share a source track, the exact landscape result can differ
  slightly from the block ledger after a disturbance. The exact run is the reported
  outcome.
- The TSA24 P58.8 subset recorded about 0.03% ledger/exact difference after
  disturbances; keep that caveat visible until the allocation seam is closed.
- Species-resolved curves, intensity-specific `ct`, and MPB severity remain
  refinements. The public package uses one CBM species per track.
- HWP lifecycle accounts are public scenario assumptions, not calibrated parameters.
  They are separate from the CBM `Products` pool and must not be added to it.

## Artifacts

Workspace handoff artifacts (not tracked in this repository) live under
`carbon-handoff/`:

- `tsa08-p120-matrix-package/`, `tsa16-p120-matrix-package/`,
  `tsa40-p120-matrix-package/`, `tsa41-p120-matrix-package/`
- `ws4-tsa08-full-50y-all/`, `ws4-tsa16-full-50y-all/`,
  `ws4-tsa40-full-50y-all/`, `ws4-tsa41-full-50y-all/`
- `ws4-tsa46-p120-fullschedule/`
- `gcbm-tsa46-500-coarse/`

The package ids, fingerprints, and hashes above are the durable identifiers.
