# TSA24 conditional-escape diagnostic

The active-spread/closed-line model capped the distribution at about 199 ha. This test added
weather-conditioned escape and a heavier escape target.

## Baseline

Twelve training tiles, 10 fires each, 50 m cells, active-spread weather, closed containment
line.

| Statistic | Historical | Closed-line |
| --- | ---: | ---: |
| median | 21.7 ha | 35.0 ha |
| p90 | 267.0 ha | 163.8 ha |
| maximum | 11,394.6 ha | 199.3 ha |
| over 500 ha | 6.9% | 0.0% |

## Conditional escape attempts

| Escape rule | Median | p90 | Maximum | Over 500 ha |
| --- | ---: | ---: | ---: | ---: |
| severity threshold 1.4, target 1,000 ha | 1,489.9 ha | 3,700.2 ha | 11,567.8 ha | 81.7% |
| severity threshold 1.8, target 1,000 ha | 34.3 ha | 5,255.6 ha | 7,230.0 ha | 46.7% |
| random 5%, target 1,000 ha | 27.3 ha | 144.4 ha | 404.3 ha | 0.0% |

The threshold rules are all-or-nothing: they either switch most fires into escape or leave
almost none. The bounded random escape target is not reached by the active-spread window, so
the escape fire stays too small.

## Finding

The model cannot yet produce a smooth, rare, large-fire tail. The escape decision and the
containment-area realization interact too strongly with the active-spread window.

This is no longer a parameter-tuning problem. The fire process needs an explicit
**survival/escape event** with its own probability and size distribution, evaluated against the
active-spread window, rather than a threshold on the same weather variables used to drive
containment.

## Boundary

Twelve training tiles, 10 fires each, 50 m cells, one fire season of weighted weather. This is a
structural diagnostic, not a calibrated regime.
