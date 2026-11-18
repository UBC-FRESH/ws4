# TSA24 block support at 50 m

The 250 m TSA24 subset dropped 1,842 intersecting blocks because they were below cell
support. This run tests a 50 m grid with a nearest-cell fallback for blocks that still miss
the raster.

## Support comparison

The same 30 km intersection contains 4,593 TSA24 blocks covering 62,897 clipped hectares.

| Cell size | Grid | Blocks represented | Valid fragments | Fragment area |
| --- | ---: | ---: | ---: | ---: |
| 250 m | 120 x 120 | 2,751 | 2,749 | 55,040.4 ha |
| 50 m | 600 x 600 | 4,593 | 4,589 | 71,107.0 ha |

At 50 m, 4,389 blocks rasterized directly. The remaining 204 were assigned to their nearest
empty cell by representative point. All 4,593 blocks are represented; four failed positive-area
loading, leaving 4,589 valid fragments.

The 50 m fuel, crown, conifer, wet-edge, and terrain layers are upsampled from the 250 m VRI
and SRTM grids. The finer grid improves block support, not the underlying spatial resolution.

## Dataset-native fire

A 240-minute FBP fire with real VRI fuel and terrain, FFMC 90.8, BUI 103.0, and 5.2 km/h wind
reached 23 fragments and burned 411.9 ha. The 50 m growth run took 11.2 s; the dataset
evaluation took 0.2 s.

## Optimizer and risk

Three burned blocks were inside the compiled `CC` window, with a combined 112.6 ha. The
optimizer reached objective `0.0` in four rounds:

- harvested area: 112.6 ha
- final volume: 9,807,231 m3
- burned area: 411.9 ha

Five fire/weather scenarios:

| Scenario | Fire (ha) | Final volume (m3) |
| --- | ---: | ---: |
| 1 | 411.9 | 9,807,135.1 |
| 2 | 279.2 | 9,812,661.6 |
| 3 | 470.1 | 9,792,183.3 |
| 4 | 502.4 | 9,789,372.1 |
| 5 | 1,193.2 | 9,721,913.6 |

The 90% lower-tail CVaR of final volume was 9,721,913.6 m3.

## Boundary

The forced nearest-cell assignments are a support device, not observed geometry. The fuel and
terrain layers are 250 m data repeated onto a 50 m grid, so this is not a 50 m inventory. The
run covers one 30 km subset and three optimized blocks.
