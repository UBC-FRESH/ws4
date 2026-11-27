> **HISTORICAL / LEGACY-MAP NOTE (2026-11-26).** This report describes the superseded frozen support map. The canonical map is the positive-overlap, cell-share map documented in `support-map-builder.md`; counts and applied results here are legacy sensitivity only.

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

## 60-minute risk run

Three 60-minute scenarios on the full estate gave:

| Scenario | Fire (ha) | Final volume (m3) |
| --- | ---: | ---: |
| 1 | 82.2 | 832,710,443.6 |
| 2 | 48.6 | 832,711,527.7 |
| 3 | 111.3 | 832,705,697.7 |

The growth source took about 30 s per scenario and the full dataset evaluation about 8.5 s.
The 90% lower-tail CVaR was 832,705,697.7 m3.

## Full-estate optimizer

Five eligible blocks were selected from the full compiled state. Their combined area was
25.7 ha. `ProcessDataset.optimize` completed four rounds:

- objective: 2.2 (23.5 ha harvested of the 25.7 ha target)
- optimizer time: 1,056.8 s
- final volume: 848,731,300 m3
- burned area: 115.325 ha
- fire events: 13

The full-state optimizer is not yet practical for routine iteration; it is roughly 17 minutes
for four rounds on this host.

## Boundary

The full-estate fire uses homogeneous fuel and flat terrain, not full TSA24 VRI/SRTM layers.
The runs are bounded tests, not fire-regime or suppression runs. The support map's small-block
weights are cell shares, not sub-cell geometry.
