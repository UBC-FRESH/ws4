# TSA24 VRI fuel-grid growth pilot

Date: 2026-11-17
Related: `notes/reports/tsa24-fire-regime-comparison.md`,
`notes/design/ws4-process-fire-regime.md`

## Source

VRI forest vegetation polygons from the BC Data Catalogue WFS layer
`WHSE_FOREST_VEGETATION.VEG_COMP_LYR_R1_POLY`, 20 km tile
`1100000,1030000,1120000,1050000` in EPSG:3005.

The VRI layer is published under the Open Government Licence - British Columbia. The raw
polygons are not copied into this repository. The BC Wildfire fuel-type layer was not used
because it is Access Only; the fuel assignment comes from WS4's documented VRI-to-FBP mapping.

## Method

- 3,063 VRI polygons in the tile; 2,724 forest stands with a leading species were mapped.
- Species percentages were normalized to conifer/deciduous fractions.
- Leading-species aliases used for the pilot: `PLI -> PL`, `FDI -> FD`, `ACT -> AC`,
  `SB -> SX`, `BB -> AT`, `LW -> LT`.
- WS4's `map_vri_table` assigned an FBP fuel type, crown closure, and burnable flag.
- A 250 m grid (80 x 80) was rasterized from the VRI polygons.
- 5,034 cells were burnable.

Fuel-type cell counts:

| Fuel type | Cells |
| --- | ---: |
| D1 | 1,215 |
| C4 | 898 |
| C2 | 692 |
| C1 | 509 |
| M1 | 473 |
| M2 | 413 |
| C3 | 359 |
| C7 | 351 |
| M4 | 97 |
| M3 | 27 |

## Growth result

One ignition at a central burnable cell, C2 fallback label, FFMC 90, BUI 60, 20 km/h wind,
flat ground, 240-minute growth:

- burned area: **350 ha**
- burned cells: **56**
- head rate of spread: **9.01 m/min**

The homogeneous C2 case on a full TSA raster produced 925 ha for the same duration. Real
fuel heterogeneity reduces the perimeter, which is the expected direction.

## Terrain

SRTM terrain (AWS Terrain Tiles) was resampled to the same 250 m EPSG:3005 grid. The tile is
gentle: elevation 710-957 m, mean slope 2.5%, maximum 20%. With the homogeneous C2 case,
flat ground burned 975 ha and the DEM slope/aspect grid burned 1,006 ha.

## Weather

Hourly Open-Meteo reanalysis at 54.35 N, 124.30 W was reduced to 13:00 daily observations and
run through the FWI System for 2023-05-01 to 2023-09-30. The hottest day was 2023-07-13:

- temperature 27.3 C
- relative humidity 23%
- wind 6.8 km/h
- FFMC 93.8
- BUI 108.2
- FWI 33.4

The VRI fuel grid, DEM slope/aspect, and that weather state together produced **1,075 ha**,
172 cells, and head ROS **8.25 m/min**. The same fuel/terrain with FFMC 90, BUI 60 and 20 km/h
wind produced 350 ha.

## Water and wet lines

The same VRI tile contains 97 non-vegetated polygons; 86 are lake, river, reservoir, or lake
shoreline features. At 250 m they occupy **463 cells**, and **329 forest-edge cells** are
within one cell of water.

One ignition on a wet forest edge, FFMC 90, BUI 60, 20 km/h wind, 240 minutes:

- dry fuel: **68.8 ha**, 11 cells
- wet-edge depth 1.0 mm, 1,440-minute decay, 0.75 mm suppression threshold:
  **25.0 ha**, 4 cells

The wet line cuts the perimeter by about 64%. This is the existing `GrowthConfig` water-depth
and suppression path, driven by real VRI water polygons.

## Multi-day weather

A four-day FWI sequence for 2023-07-12 to 2023-07-15 was used as `WeatherStep` intervals:
FFMC 92.6-93.8, BUI 102.8-116.9, wind 2.7-7.8 km/h. On an 80 x 80, 250 m homogeneous C2 grid
the free-burn case filled the entire 40,000 ha tile within four days.

## Containment

To isolate the containment timing, an 80 x 80, 250 m homogeneous C2 grid used the hot
2023-07-13 state (FFMC 93.8, BUI 108.2, wind 6.8 km/h) for 12 hours. A closed ring at about
2.5 km radius was assigned different completion times:

| Line completion | Burned area | Cells |
| ---: | ---: | ---: |
| 0 min | 1,556 ha | 249 |
| 60 min | 1,556 ha | 249 |
| 120 min | 1,556 ha | 249 |
| 180 min | 19,038 ha | 3,046 |
| 240 min | 25,325 ha | 4,052 |
| 360 min | 25,531 ha | 4,085 |

The free-burn 12-hour case was 25,531 ha. In this weather, the line contains the fire only if
it closes within about two hours; after three hours the fire has crossed the line and the
containment has little effect.

## Real-layer ensemble

Fifty simulated fires on the 20 km VRI/DEM tile, using:

- real fuel, crown closure, conifer fraction
- real slope, aspect, elevation
- VRI water-edge wetting
- daily 2023 FWI weather sampled from May–September
- random ignition cell and duration of 4, 8, 12, or 24 hours

Results:

| Statistic | Simulated | Historical tile |
| --- | ---: | ---: |
| fires | 50 | 7 |
| mean | 961.5 ha | 58.8 ha |
| median | 65.6 ha | 49.9 ha |
| p90 | 2,885.6 ha | 104.2 ha |
| maximum | 14,668.8 ha | 139.9 ha |

The median is close, but the simulated tail is far too heavy. The historical tile sample is
small (seven fires in 75 years), so the comparison has wide uncertainty, but the large-fire
tail is not reproduced by this duration/weather sampling.

## Boundary

The multi-day weather run is homogeneous C2 and flat; the containment run is a single hot
weather state. The real-layer ensemble has real fuel, terrain, water, and weather, but samples
duration uniformly and does not model containment or suppression crews. It is not a calibrated
regime.
