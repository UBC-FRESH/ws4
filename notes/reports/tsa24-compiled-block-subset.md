# TSA24 actual compiled inventory: 30 km block subset

This run replaces the synthetic tile inventory with the actual TSA24 compiled block inventory.
It is a 30 km spatial subset, not the full 458,708-block estate.

## Spatial subset

The full TSA24 compiled artifact contains 458,708 blocks and 5,899,679.6 ha. Its block geometry
is available for every block, so the blocks can be rasterized into a fire grid.

The existing 30 km real-layer tile intersects 4,593 TSA24 blocks covering 62,897 ha. A 250 m
rasterization retained 2,751 fragments and 55,040.4 ha; 2,749 blocks survived dataset loading
as valid fragments.

The subset dataset loads in 0.9 s with 5,639 species cohorts. The full artifact loads in 131 s
and about 2 GB, which is why the spatial subset is used for the optimizer and risk runs.

## Dataset-native fire

The fire source was built from the dataset's fragment raster and the real VRI/SRTM/water
layers on the 30 km tile:

- FFMC 93.8, BUI 108.2, wind 6.8 km/h at 270 degrees
- 240 minutes
- 44 reached fragments
- 1,069 ha burned

A one-year dataset run reported:

| Account | Value |
| --- | ---: |
| `bridge.volume_m3` | 6,947,129 |
| `state.biomass_t` | 3,798,148 |
| `fire.burned_area_ha_total` | 1,069.0 |
| `fire.count_total` | 44 |

## Optimizer

Six burned blocks were inside the compiled `CC` age window. Their combined area was 166.5 ha.
`ProcessDataset.optimize` used the growth source and a 166.5 ha harvest target:

- completed seven rounds
- objective: `0.0`
- harvested area: 166.5 ha
- final volume: 7,127,369 m3
- final biomass: 3,963,752 t
- burned area: 1,069 ha

## Risk ensemble

Five scenarios varied the ignition cell and weather. The same six-block schedule ran for three
years.

| Scenario | Fire (ha) | Final volume (m3) |
| --- | ---: | ---: |
| 1 | 445.4 | 7,167,038.8 |
| 2 | 498.9 | 7,167,208.5 |
| 3 | 328.9 | 7,181,115.0 |
| 4 | 6.2 | 7,195,334.7 |
| 5 | 798.1 | 7,153,768.1 |

The 90% lower-tail CVaR of final volume was 7,153,768.1 m3.

## Boundary

The subset retains only blocks whose geometry rasterizes at 250 m; 1,842 of the 4,593
intersecting blocks were below that support and were dropped. The fire and risk runs use one
30 km tile, six harvested blocks, and five scenarios. The full TSA24 fragment raster has not
been built.
