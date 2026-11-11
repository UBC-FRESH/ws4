# P170 reanalysis weather consistency

Date: 2026-11-11
Phase: P170 (#1011)
Task: P170.2 (#1013)
Manifest: `notes/reports/p170-fwi-consistency.json`
CSV: `notes/reports/p170-fwi-consistency.csv`

## Result

Daily reanalysis-derived FWI is close to CFSDS on FFMC and ISI, but BUI is higher.
This does not explain a 10-14x area bias.

| Summary | Value |
| --- | ---: |
| Days compared | 68 |
| Median absolute FFMC delta | 0.77 |
| Max absolute FFMC delta | 21.77 |
| Median absolute BUI delta | 11.62 |
| Max absolute BUI delta | 41.81 |
| Median absolute ISI delta | 0.88 |
| Max absolute ISI delta | 7.90 |
| Days reanalysis ISI higher | 56 of 68 |

## Per-case medians

| Case | Median FFMC delta | Median ISI delta | Days ISI higher |
| --- | ---: | ---: | ---: |
| 2003_526 | 1.14 | 0.50 | 12/16 |
| 2003_706 | 0.68 | 0.48 | 2/5 |
| 2009_147 | 0.69 | 0.97 | 2/2 |
| 2009_79 | 2.59 | 3.70 | 2/2 |
| 2023_19 | 1.91 | 1.15 | 15/15 |
| 2023_786 | 0.72 | 1.25 | 23/28 |

## Interpretation

- FFMC is close: median absolute delta below 1 code.
- ISI is close: median absolute delta below 1, though reanalysis is higher on most days.
- BUI is systematically higher, but BUI is not the dominant ROS driver in FBP; it cannot alone explain 10x area.
- Some individual days have large deltas, so weather is not perfect, but the pattern is not a 10x scale error.
- Weather/FFMC is not the primary cause. The next test is containment/stopping.

## Decision

Do not replace the weather source yet. Proceed to a containment/stopping mechanism or
a daily event-timing correction. P164.3 remains paused.
