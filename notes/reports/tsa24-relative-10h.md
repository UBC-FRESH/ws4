# TSA24 relative suppression with a 10-hour active day

Full-day active spread made potential fires unrealistically large. This run uses 10 active
hours per day and refits the relative retained fractions on the fixed potential sample.

## Potential growth

- median potential: about 22,600 ha
- p90 potential: about 79,800 ha
- maximum potential: about 87,000 ha

## Fitted parameters

- contained retained fraction: `0.001253` median, `1.446` log-sigma
- escaped retained fraction: `0.8549` median, `0.113` log-sigma
- escape cap: `12,000 ha`
- escape hazard intercept: `-4.663`
- duration/FWI/BUI/wind weights: `0.5`, `0.2`, `0.1`, `0.1`

## Training

| Statistic | Historical first 12 | Fitted |
| --- | ---: | ---: |
| median | 21.7 ha | 26.1 ha |
| p90 | 267.0 ha | 263.5 ha |
| p95 | 809.7 ha | 467.1 ha |
| over 100 ha | 21.6% | 22.5% |
| over 500 ha | 6.9% | 5.0% |
| over 1,000 ha | 4.4% | 2.9% |
| over 5,000 ha | 1.5% | 2.1% |
| maximum | 11,394.6 ha | 12,000.0 ha |

## Held-out validation

| Statistic | Historical last 12 | Validation |
| --- | ---: | ---: |
| median | 27.9 ha | 25.2 ha |
| p90 | 1,266.2 ha | 218.9 ha |
| p95 | 3,309.8 ha | 619.5 ha |
| over 100 ha | 30.3% | 25.4% |
| over 500 ha | 12.7% | 6.2% |
| over 1,000 ha | 11.0% | 3.8% |
| over 5,000 ha | 4.4% | 2.5% |
| maximum | 25,114.8 ha | 12,000.0 ha |

The central tendency transfers much better than the global fit, but the held-out tail is still
underproduced by about a factor of three to four.

## Finding

A 10-hour active day fixes the potential-growth scale and produces a credible central
distribution. The remaining error is the tail: the fixed 12,000 ha escape cap and the global
escape hazard are too restrictive for the validation tiles.

The next fit should make the escape cap and escape fraction tile-dependent, or at least allow
the cap to exceed 12,000 ha for the highest-hazard tiles.

## Boundary

Twenty fires per tile at 250 m; potential and historical samples are clipped to 30 km tiles.
This is a calibration diagnostic, not a finished regime.
