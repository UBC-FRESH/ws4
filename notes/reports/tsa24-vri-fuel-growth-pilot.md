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

## Boundary

Slope, weather time series, wet lines, containment, and suppression are still scalar defaults.
The result demonstrates the real VRI fuel/crown layer in the growth engine; it is not a
calibrated fire regime.
