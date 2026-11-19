# TSA24 duration-tail diagnostic

The combined-12 fit used 50 m runs with durations capped at 1.46 days. That was inconsistent
with the 24-tile baseline, which used local incident durations up to 8.75 days. This test
restored the longer duration tail in the combined-12 training set.

## Result

| Statistic | Historical | Extended-duration run |
| --- | ---: | ---: |
| fires | 204 | 120 |
| mean | 258.2 ha | 2,393.0 ha |
| median | 21.7 ha | 0.25 ha |
| p90 | 267.0 ha | 370.3 ha |
| p95 | 809.7 ha | 18,891.2 ha |
| maximum | 11,394.6 ha | 79,423.8 ha |
| over 100 ha | 21.6% | 20.0% |
| over 500 ha | 6.9% | 8.3% |
| over 1,000 ha | 4.4% | 8.3% |

Long durations restore the tail, but they also produce an extremely heavy upper tail and leave
most fires at the one-cell floor under the sampled weather.

## Finding

Incident out-dates include mop-up and patrol. They are not active-spread durations. Using them
as fire-growth duration lets a few fires grow for many days while low-danger days still stop
most fires at ignition.

The calibration needs an active-spread duration distribution, or a duration conditioned on
fire weather, rather than raw incident elapsed time.

## Boundary

Twelve training tiles, 10 fires each, 50 m cells, fire-danger-weighted weather, one fire season.
This is a diagnostic, not a calibrated regime.
