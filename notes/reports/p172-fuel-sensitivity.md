# P172 fuel-map sensitivity

Date: 2026-11-11
Phase: P172 (#1021)
Task: P172.2 (#1023)
Manifest: `notes/reports/p172-fuel-sensitivity.json`
CSV: `notes/reports/p172-fuel-sensitivity.csv`

## Result

Homogeneous dominant fuel does not remove the overprediction.
Median per-cell ratio 10.35x; median homogeneous ratio 10.25x; only 2 of 6 cases
changed slightly. Fuel heterogeneity is not the cause.

| Case | Dominant fuel | Per-cell ratio | Homogeneous ratio |
| --- | --- | ---: | ---: |
| 2003_526 | C3 | 10.24x | 10.24x |
| 2003_706 | C3 | 10.25x | 10.25x |
| 2009_147 | M1 | 11.73x | 11.16x |
| 2009_79 | M1 | 10.44x | 10.08x |
| 2023_19 | D1 | 9.77x | 9.77x |
| 2023_786 | C3 | 12.60x | 12.60x |

Cases improved by homogeneous fuel: 2 of 6.

## Interpretation

- Per-cell fuel and dominant homogeneous fuel produce nearly the same area.
- The remaining explanations are suppression/containment or a genuine ROS-scale issue.
- A global fuel or ROS multiplier is not justified by this result.
