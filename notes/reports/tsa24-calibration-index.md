# TSA24 fire calibration index

This is the entry point for the fire calibration work. It records the experiment sequence,
reports, code commits, local analysis scripts, and the current handoff state.

## Current state

- Code baseline: `9918fb17` on `main`
- Worktree: `worktrees/ws4-calibration`
- Calibrated region map: `work/fire_regime/results/region-calibration.json` (tracked)
- Full-layer cache: `work/fire_regime/data/tsa24-full-layers` (local, Git-ignored)
- Full-layer DEM cache: `work/fire_regime/data/dem` (local, Git-ignored)
- Local analysis scripts: `work/fire_regime/`
- These scripts are local analysis code, not part of the package contract
- Reports are under `notes/reports/`

The calibrated estate API is tracked in `ws4/ecosystem/estate_fire.py` and exported from
`ws4.ecosystem`. The handoff report is
`notes/reports/p164-8-estate-handoff.md`.

## Entry points

| Purpose | Location |
| --- | --- |
| Build a calibrated fire source from the layer stack | `ws4.ecosystem.build_estate_fire_source` |
| Load the tiled layer stack | `ws4.ecosystem.load_estate_grid` |
| Load the regional suppression map | `ws4.ecosystem.load_calibrated_regions` |
| Handoff summary and boundaries | `notes/reports/p164-8-estate-handoff.md` |
| Regional calibration evidence | `notes/reports/p164-8-region-calibration.md` |
| Full-estate integration evidence | `notes/reports/p164-8-regional-estate-integration.md` |
| Real-layer integration evidence | `notes/reports/p164-8-real-layer-estate.md` |
| Risk ensemble result | `work/fire_regime/results/risk-ensemble-5seed.json` |
| Full-layer five-year case | `work/fire_regime/results/estate-case-5yr-full-layers.json` |
| Bounded regional optimizer | `work/fire_regime/results/optimizer-regional.json` |
| Full-estate sharded optimizer | `work/fire_regime/results/optimizer-full-estate.json` |
| Full-estate schedule | `work/fire_regime/results/optimizer-full-estate-schedule.csv` |
| Transfer validation | `notes/reports/p164-8-transfer-validation.md` |
| Hierarchical validation | `notes/reports/p164-8-hierarchical-validation.md` |
| Benchmark and reproducibility package | `notes/reports/p164-8-benchmark-reproducibility.md` |
| Artifact manifest | `work/fire_regime/results/reproducibility-manifest.json` |
| Data licences | `notes/reports/p164-8-data-licenses.md` |

## Scripts

| Script | Purpose |
| --- | --- |
| `six_tiles.py` | Six-tile VRI/SRTM fetch and real-versus-homogeneous fire comparison |
| `regime24.py` | 24-tile real-layer fire ensemble and historical comparison |
| `tier24.py` | Three-tier suppression sweep |
| `continuous24.py` | Continuous containment-area sweep |
| `fine50.py` | 50 m fire-grid and active-spread experiments |
| `build_full_layers.py` | 133-tile full-TSA24 layer cache with a resumable manifest |
| `risk_ensemble.py` | Five-seed calibrated risk ensemble on the full layer stack |
| `optimizer_regional.py` | Bounded optimizer in region `t13` |
| `full_estate_optimizer.py` | Sharded full-estate optimizer and aggregate evaluation |

The scripts depend on public VRI, SRTM, and BC Wildfire sources. Cache and output locations are
local and are not part of the repository contract.

## Calibration sequence

| Step | Evidence | Commit |
| --- | --- | --- |
| VRI fuel and SRTM six-tile pilot | `notes/reports/tsa24-vri-fuel-growth-pilot.md` | `a2f75d7b` |
| 24-tile real-layer regime calibration | `notes/reports/tsa24-24-tile-regime.md` | `98e96ced` |
| Three-tier suppression sweep | `notes/reports/tsa24-three-tier-calibration.md` | `96003e3c` |
| Continuous containment and resolution limit | `notes/reports/tsa24-continuous-containment-resolution.md` | `9128ec7f` |
| 50 m fire-grid calibration | `notes/reports/tsa24-fine50-fire-grid.md` | `f8900415` |
| 50 m hot-weather diagnostic | `notes/reports/tsa24-fine50-hot-weather.md` | `c615f80e` |
| Weighted-weather containment | `notes/reports/tsa24-weighted-weather-containment.md` | `a7681693` |
| Compressed tile dataset and optimizer | `notes/reports/tsa24-compiled-tile-optimizer.md` | `a65b06d` |
| TSA24 block subset optimizer and risk | `notes/reports/tsa24-compiled-block-subset.md` | `7284e2f1` |
| 50 m block-support policy | `notes/reports/tsa24-block-support-50m.md` | `24f514a9` |
| Full-estate support and fire path | `notes/reports/tsa24-full-estate-support.md` | `12eb4f89` |
| Active-spread closed-line diagnostic | `notes/reports/tsa24-active-spread-contained.md` | `05692c67` |
| Conditional-escape diagnostic | `notes/reports/tsa24-conditional-escape-diagnostic.md` | `28f0f6f8` |
| Relative suppression fit and validation | `notes/reports/tsa24-relative-suppression-fit.md` | `af1be150` |
| 10-hour active-day relative fit | `notes/reports/tsa24-relative-10h.md` | `20d3c320` |
| Region-level suppression fit | `notes/reports/tsa24-region-suppression.md` | `063fda14` |
| Active spread hours | `ws4/ecosystem/growth_fire.py` | `7110541e` |
| Region-level suppression support | `ws4/ecosystem/growth_fire.py` | `1d46d410` |
| Tail-fire audit with antecedent FWI | `notes/reports/tsa24-tail-audit.md` | `2b694256` |
| P164.8 protocol | `notes/design/ws4-regime-calibration-protocol.md` | `93db5099` |
| P164.8 calibration harness | `ws4/fire/regime_calibration.py` | `a950d7dd` |
| P164.8 global gate no-go | `notes/reports/p164-8-regime-calibration.md` | `521d6aef` |
| Regional calibration map | `notes/reports/p164-8-region-calibration.md` | `a05de38d` |
| Regional estate integration | `notes/reports/p164-8-regional-estate-integration.md` | `21595f8a` |
| Real-layer estate integration | `notes/reports/p164-8-real-layer-estate.md` | `209962e2` |
| Support-coverage correction | `notes/reports/p164-8-real-layer-estate.md` | `c18e8357` |
| Calibrated estate handoff API | `notes/reports/p164-8-estate-handoff.md` | `9918fb17` |
| Transfer validation diagnostic | `notes/reports/p164-8-transfer-validation.md` | `7a255e55` |
| Hierarchical validation diagnostic | `notes/reports/p164-8-hierarchical-validation.md` | `4e63ac46` |

## Key parameters and seeds

- 250 m and 50 m fire grids
- 10 active spread hours per day
- 90-day antecedent FWI spin-up for tail events
- relative contained/escaped fractions
- escape caps up to 30,000 ha in the region-level fit
- regional calibration seed `20261121`
- risk and integration run seeds are recorded in the result JSON files

## Data sources

- BC VRI WFS: forest vegetation polygons and crown/species attributes
- SRTM elevation via public terrain tiles
- BC Wildfire perimeters and historical incident records
- public TSA24 compiled inventory and block geometry

## Boundary

The regional calibration is in-sample for the fixed 24 tiles. The full layer cache covers all
support cells, but the calibrated suppression map has 24 regions and a median default outside
them. The five-seed risk result is a small tail sample. The full-estate optimizer is sharded and
bounded: 112 of 133 tiles had eligible CC blocks, up to 20 blocks per tile, and each shard used a
local harvest target. It is not a global joint optimum.

Large layer and DEM caches are local and Git-ignored. Their paths are recorded above so another
session on this host can reuse them without copying them into Git.
