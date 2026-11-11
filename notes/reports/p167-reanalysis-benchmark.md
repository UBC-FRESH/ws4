# P167 reanalysis event benchmark

Date: 2026-11-11
Phase: P167 (#996)
Task: P167.2 (#998)
Manifest: `notes/reports/p167-reanalysis-benchmark.json`
CSV: `notes/reports/p167-reanalysis-benchmark.csv`

## Result

6 independent CFSDS cases were run with the same uncalibrated protocol.
All six overpredicted area. The P166 case is not an outlier.

| Summary | Value |
| --- | ---: |
| Median IoU | 0.096 |
| Best IoU | 0.127 |
| Worst IoU | 0.079 |
| Median area bias | +9.25x |
| Area bias range | +6.68x to +11.60x |
| Overpredicted cases | 6 of 6 |

## Per-case result

| Case | IoU | Sorensen | Area bias | Perimeter bias | Centroid m |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2003_526 | 0.096 | 0.175 | +9.24x | +4.96x | 175 |
| 2003_706 | 0.095 | 0.174 | +9.25x | +2.54x | 644 |
| 2009_147 | 0.127 | 0.225 | +6.68x | +1.48x | 313 |
| 2009_79 | 0.096 | 0.175 | +9.43x | +0.69x | 299 |
| 2023_19 | 0.097 | 0.176 | +8.77x | +7.13x | 30 |
| 2023_786 | 0.079 | 0.147 | +11.60x | +2.75x | 678 |

## Interpretation

- The failure is systematic, not driven by the P166 case.
- Every case overpredicts final area by roughly 7x to 12x.
- Overlap is uniformly poor: best IoU 0.127, median 0.096.
- Centroid errors are comparatively modest (30-678 m), so the main failure is scale and shape, not gross displacement.
- Perimeter bias ranges from +0.69x to +7.13x, so perimeter error is not a single constant factor.

## Protocol

- CFSDS final scar and first-day burned centroid.
- FireSTARR FBP fuel and terrain tile 11_0.
- Open-Meteo hourly reanalysis weather.
- CFSDS event-day FFMC and BUI as starting codes.
- No calibration, multipliers, or case-specific fuel changes.

## Decision

P167 establishes a systematic overprediction baseline. The next work should diagnose scale
and shape using process checks, not tune a multiplier to one fire. P164.3 remains paused.

## Limits

- Six cases, all from one fuel/terrain tile.
- Reanalysis weather and daily perimeters.
- Reconstructed ignition.
- No station-observed hourly cases were added.
