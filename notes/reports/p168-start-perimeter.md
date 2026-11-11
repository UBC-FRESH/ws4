# P168 start-perimeter event benchmark

Date: 2026-11-11
Phase: P168 (#1001)
Task: P168.2 (#1003)
Manifest: `notes/reports/p168-reanalysis-first-perimeter.json`
CSV: `notes/reports/p168-reanalysis-first-perimeter.csv`

## Result

First-perimeter seeding did **not** remove the systematic overprediction.
The median IoU stayed at 0.095, and area bias remained +8.77x to +11.60x.

| Case | Start cells | Point IoU | Perimeter IoU | Perimeter area bias |
| --- | ---: | ---: | ---: | ---: |
| 2003_526 | 1 | 0.096 | 0.096 | +9.24x |
| 2003_706 | 550 | 0.095 | 0.095 | +9.25x |
| 2009_147 | 588 | 0.127 | 0.083 | +10.73x |
| 2009_79 | 280 | 0.096 | 0.096 | +9.44x |
| 2023_19 | 5 | 0.097 | 0.097 | +8.77x |
| 2023_786 | 5 | 0.079 | 0.079 | +11.60x |

## Interpretation

- The P166/P167 point ignition was a protocol flaw, but it is not the main cause of the 10x area bias.
- Cases with hundreds of start cells still overpredict by roughly 9-11x.
- The model fills large connected burnable areas; the observed fires stop far short of that.
- This points to missing containment/stopping and/or a scale error in the growth kernel, not to the ignition seed alone.
- No calibration multiplier was applied.

## Decision

P168 rules out point ignition as the dominant cause. The next diagnosis should examine
containment/stopping, observed growth timing, and the growth kernel scale. P164.3 remains paused.
