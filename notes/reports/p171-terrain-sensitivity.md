# P171 terrain sensitivity

Date: 2026-11-11
Phase: P171 (#1016)
Task: P171.2 (#1018)
Manifest: `notes/reports/p171-terrain-sensitivity.json`
CSV: `notes/reports/p171-terrain-sensitivity.csv`

## Result

Flat terrain produced the same area and IoU as DEM terrain in all six cases.
Terrain is not the cause of the overprediction in this path.

| Case | DEM ratio | Flat ratio | DEM IoU | Flat IoU |
| --- | ---: | ---: | ---: | ---: |
| 2003_526 | 10.24x | 10.24x | 0.096 | 0.096 |
| 2003_706 | 10.25x | 10.25x | 0.095 | 0.095 |
| 2009_147 | 11.73x | 11.74x | 0.083 | 0.083 |
| 2009_79 | 10.44x | 10.44x | 0.096 | 0.096 |
| 2023_19 | 9.77x | 9.77x | 0.097 | 0.097 |
| 2023_786 | 12.60x | 12.60x | 0.079 | 0.079 |

Median DEM ratio: 10.35x. Median flat ratio: 10.35x.
Cases where flat reduced the ratio: 0 of 6.

## Interpretation

- Slope/aspect is not driving the 10x area bias.
- The remaining candidates are fuel mapping, ROS scale, or containment/stopping.
- No calibration was applied.
