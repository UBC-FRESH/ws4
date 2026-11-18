# TSA24 full-estate support and fire path

This run validates the area-weighted support map against the full TSA24 compiled artifact and
runs the growth fire through the resulting full-estate dataset.

## Full-estate dataset

The support map represents all 458,708 TSA24 blocks:

- grid: 1,957 by 2,237 cells at 250 m
- 1,111,565 burnable support cells
- 1,310,129 fragment memberships
- 458,419 valid dataset blocks after positive-area loading
- 942,587 species cohorts
- full artifact load: 154 s

`ProcessDataset` now accepts either a single-valued fragment raster or a `FragmentSupport`
grid. The support map passes the dataset fragment-presence check.

## Full-estate fire path

A bounded growth fire was run on the full support grid with homogeneous C2 fuel and flat
terrain:

- FFMC 93.8, BUI 108.2, wind 6.8 km/h at 270 degrees
- 30 minutes
- 7 reached fragments
- 43.75 ha burned
- growth source: 30.4 s
- full-estate dataset evaluation: 8.9 s

One-year full-estate accounts:

| Account | Value |
| --- | ---: |
| `bridge.volume_m3` | 832,716,200 |
| `state.biomass_t` | 457,899,600 |
| `state.fuel_t` | 68,684,940 |
| `fire.burned_area_ha_total` | 43.75 |
| `fire.count_total` | 7 |

## Boundary

The full-estate fire uses homogeneous fuel and flat terrain, not full TSA24 VRI/SRTM layers.
The run is a 30-minute bounded test, not a fire-regime or suppression run. The support map's
small-block weights are cell shares, not sub-cell geometry.
