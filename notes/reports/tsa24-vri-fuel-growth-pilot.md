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

## Boundary

This is a single weather state, not a time-dependent weather sequence. Containment and
suppression crews are not yet represented; the wet-line result uses the water-depth threshold.
The result demonstrates real VRI fuel, SRTM terrain, FWI weather, and water-edge suppression
in the growth engine; it is not a calibrated fire regime.
