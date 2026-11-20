# TSA24 region-level suppression calibration

The global relative fraction failed to transfer. This run fitted suppression per tile using each
tile's historical quantiles and potential sample.

## Aggregate result

| Statistic | Historical | Per-region fit |
| --- | ---: | ---: |
| median | 23.0 ha | 31.8 ha |
| p90 | 490.2 ha | 618.5 ha |
| p95 | 1,918.9 ha | 1,156.0 ha |
| over 100 ha | 26.2% | 29.7% |
| over 500 ha | 10.0% | 11.8% |
| over 1,000 ha | 7.9% | 6.2% |
| over 5,000 ha | 3.0% | 0.1% |
| maximum | 25,114.8 ha | 6,709.9 ha |

The median, p90, and over-100/500/1,000 fractions are now in the right range. The extreme tail
is still missing.

## Method

For each tile with at least five historical fires:

- contained fraction = historical median / potential median
- escaped fraction = historical p90 / potential p90
- escape cap = 1.1 × historical maximum, bounded to 12,000–30,000 ha
- escape probability = historical fraction over 500 ha
- hazard intercept adjusted by the tile's mean fire-weather severity

Twenty potential samples per tile were generated with a 10-hour active day.

## Finding

Region-level fractions fix the central distribution but not the extreme maximum. The cap and
hazard allow medium fires, yet the potential sample / escape draw does not reach the 10,000–
25,000 ha events.

The remaining gap is in the **escape-size realization**, not the contained fraction. The model
needs an escape path that can reach the historical maximum when the potential and weather are
extreme.

## Boundary

The per-tile values are empirically fitted on all 24 tiles, so this is not an independent
holdout test. The 30 km tile sample and 2023 weather remain limiting.
