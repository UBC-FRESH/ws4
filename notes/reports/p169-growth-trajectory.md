# P169 growth trajectory diagnosis

Date: 2026-11-11
Phase: P169 (#1006)
Task: P169.2 (#1008)
Manifest: `notes/reports/p169-growth-trajectory.json`
CSV: `notes/reports/p169-growth-trajectory.csv`

## Result

The model is close to observed area on day 1, but diverges by day 2 and ends 10-14x
too large. Radius 1 does not fix the bias.

| Case | Day 1 ratio | Final ratio, radius 2 | Final ratio, radius 1 | First day >2x |
| --- | ---: | ---: | ---: | ---: |
| 2003_526 | 1.23x | 10.44x | 10.44x | 2 |
| 2003_706 | 1.05x | 11.64x | 11.64x | 2 |
| 2009_147 | 1.04x | 12.50x | 12.16x | 2 |
| 2009_79 | 1.09x | 13.05x | 13.05x | 2 |
| 2023_19 | 1.23x | 10.77x | 10.77x | 2 |
| 2023_786 | 1.03x | 13.77x | 13.77x | 2 |

| Summary | Value |
| --- | ---: |
| Median day-1 ratio | 1.07x |
| Median final ratio, radius 2 | 12.07x |
| Median final ratio, radius 1 | 11.90x |
| Cases >2x at day 1 | 0 |
| Cases >2x at final, radius 2 | 6 |
| Cases >2x at final, radius 1 | 6 |

## Interpretation

- Initial growth is approximately correct: median day-1 ratio 1.07x.
- Divergence begins by day 2 in every case.
- The final area is 10.4x to 13.8x observed.
- Reducing neighbor radius from 2 to 1 does not change the final bias.
- Therefore the dominant issue is late/continued growth, not the ignition seed or neighbor radius.
- The likely causes are missing containment/stopping, an event-timing mismatch, or excessive daily weather-driven growth.

## Decision

P169 narrows the structural failure to **late growth**. The next fix should model
containment/stopping or verify the daily weather/FFMC sequence, not apply a global ROS
multiplier. P164.3 remains paused.
