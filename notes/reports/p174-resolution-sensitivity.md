# P174 large-fire resolution sensitivity

Date: 2026-11-11
Phase: P174 (#1031)
Task: P174.2 (#1033)
Manifest: `notes/reports/p174-resolution-sensitivity.json`
CSV: `notes/reports/p174-resolution-sensitivity.csv`

## Result

Fine grids reduce the large-fire bias only modestly. The residual is not just a 500 m artifact.

| Case | 500 m IoU | 100 m IoU | 500 m area bias | 100 m area bias |
| --- | ---: | ---: | ---: | ---: |
| 2003_96 | 0.192 | 0.209 | +4.12x | +3.67x |
| 2003_663 | 0.350 | 0.387 | +1.67x | +1.39x |

## Interpretation

- `2003_96`: area bias improves from 4.12x to 3.67x; IoU from 0.192 to 0.209.
- `2003_663`: area bias improves from 1.67x to 1.39x; IoU from 0.350 to 0.387.
- Resolution explains part of the bias, but a 1.4x-3.7x residual remains.
- The next step is a residual ROS audit or containment, not a calibration multiplier.
