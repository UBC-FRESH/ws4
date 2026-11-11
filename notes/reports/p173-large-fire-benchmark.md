# P173 large-fire reanalysis benchmark

Date: 2026-11-11
Phase: P173 (#1026)
Task: P173.2 (#1028)
Manifest: `notes/reports/p173-large-fire-benchmark.json`
CSV: `notes/reports/p173-large-fire-benchmark.csv`

## Result

The large-fire bias is much smaller than the small-fire bias: median area bias
2.89x vs 9.25x, and median IoU
0.238 vs 0.096.
This supports small-fire suppression as a major cause, with residual overprediction.

| Case | IoU | Sorensen | Area bias | Perimeter bias | Centroid m |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2003_96 | 0.192 | 0.322 | +4.12x | +0.81x | 186 |
| 2003_663 | 0.350 | 0.518 | +1.67x | +0.56x | 7705 |
| 2023_331 | 0.265 | 0.419 | +2.15x | +7.19x | 3364 |
| 2023_366 | 0.211 | 0.349 | +3.64x | +0.21x | 3013 |

## Small vs large

| Group | Cases | Median IoU | Median area bias | Best area bias | Worst area bias |
| --- | ---: | ---: | ---: | ---: | ---: |
| Small | 6 | 0.096 | +9.25x | +6.68x | +11.60x |
| Large | 4 | 0.238 | +2.89x | +1.67x | +4.12x |

## Interpretation

- Large fires still overpredict, but by about 1.7x to 4.1x rather than 7x to 12x.
- The large-fire median IoU is 0.238, compared with 0.096 for small fires.
- This is consistent with small fires being strongly suppression-dominated.
- Residual large-fire bias remains, so suppression is not the only issue.
- The large cases use a coarse 500 m grid, so this is distribution evidence, not fine-scale validation.

## Decision

Add a containment/stopping mechanism for small fires, and audit the residual large-fire
ROS scale. P164.3 remains paused.
