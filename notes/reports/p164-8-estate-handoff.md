# P164.8 calibrated estate handoff

Status: handoff

This is the closeout for the calibrated TSA24 fire regime and its estate integration. The
calibrated fire source is available from the tracked API; the large layer cache and the local
analysis scripts remain on the work host.

## Tracked entry point

The API is merged on `main` as `9918fb17`:

- `ws4/ecosystem/estate_fire.py`
- `ws4.ecosystem.build_estate_fire_source`
- `ws4.ecosystem.load_estate_grid`
- `ws4.ecosystem.load_calibrated_regions`

Minimal use:

```python
from pathlib import Path
from ws4.ecosystem import build_estate_fire_source

source, grid, regions = build_estate_fire_source(
    support,
    layer_manifest=Path("layers/manifest.json"),
    calibration=Path("region-calibration.json"),
    tiles_manifest=Path("tiles.json"),
    origin_x=0.0,
    origin_y=0.0,
    cell_size_m=250.0,
    ignitions_by_year={0: [ignition]},
    growth=growth_config,
    seed=20261122,
)
```

The caller supplies the projected-grid origin, support grid, layer manifest, calibration JSON,
tile manifest, and ignitions. The function does not assume a workstation path.

## Layer coverage

The full layer cache is local and Git-ignored:

- `work/fire_regime/data/tsa24-full-layers/`
- 133 aligned 30 km tiles
- 1,111,565 of 1,111,565 support cells covered (100%)
- 1,012,231 forest support cells
- manifest: `work/fire_regime/data/tsa24-full-layers/manifest.json`

The cache was built from public BC VRI WFS, SRTM 1 arc-second terrain, and VRI non-vegetated
water polygons. The DEM cache is `work/fire_regime/data/dem/`. Both are local by design; the
manifest and index describe how to locate them.

## Calibration state

The calibrated suppression map is tracked at
`work/fire_regime/results/region-calibration.json`.

- 24 calibrated tile regions
- median suppression configuration outside the calibrated tiles
- in-sample calibration, no independent holdout claim
- regional result: median 23.8 ha versus 23.0 ha historical; p90 361.5 ha versus 490.2 ha;
  maximum 20,770.4 ha versus 25,114.8 ha

The earlier global gate result remains a no-go. The regional map is the usable calibration.

## Risk ensemble

`work/fire_regime/results/risk-ensemble-5seed.json`

Five seeds on the full-layer five-year schedule:

- burned-area median 7,889.6 ha; p90 8,600.8 ha
- no-fire baseline volume 822.55 million m3
- volume-loss median 0.92 million m3
- CVaR95 loss 1.04 million m3, which is the worst of five seeds

The tail estimate is limited by the five-seed sample.

## Full-layer five-year case

`work/fire_regime/results/estate-case-5yr-full-layers.json`

- 12,176 scheduled blocks
- 885 fragment-level fire events
- 8,374.1 ha burned
- 156,358.8 ha harvested
- 821.6 million m3 volume
- 463.8 million t final biomass
- full-estate evaluation completed

## Full-estate sharded optimizer

`work/fire_regime/results/optimizer-full-estate.json` and
`work/fire_regime/results/optimizer-full-estate-schedule.csv`

- 36 workers
- 112 of 133 tiles had eligible CC blocks in the five-year window
- up to 20 blocks per tile
- two local optimizer rounds per shard
- 179 scheduled blocks/events
- 20,775.6 ha harvested
- 859.98 million m3 final volume
- 74.25 ha burned; 16 fragment-level fire events
- 480.59 million t final biomass
- 655.5 s wall time

This is a sharded bounded optimizer, not a global joint optimum. Each shard used a local 10%
harvest target, and blocks were selected by area within each tile.

## Local analysis scripts

The scripts remain under `work/fire_regime/` and are not part of the package contract:

- `build_full_layers.py`
- `risk_ensemble.py`
- `optimizer_regional.py`
- `full_estate_optimizer.py`

The index records their purpose and the data sources. Their cache and logs are Git-ignored.

## Evidence map

- `notes/reports/p164-8-region-calibration.md`
- `notes/reports/p164-8-regional-estate-integration.md`
- `notes/reports/p164-8-real-layer-estate.md`
- `notes/reports/p164-8-estate-handoff.md`
- `notes/reports/tsa24-calibration-index.md`
- `work/fire_regime/results/region-calibration.json`
- `work/fire_regime/results/risk-ensemble-5seed.json`
- `work/fire_regime/results/estate-case-5yr-full-layers.json`
- `work/fire_regime/results/optimizer-regional.json`
- `work/fire_regime/results/optimizer-full-estate.json`
- `work/fire_regime/results/optimizer-full-estate-schedule.csv`
