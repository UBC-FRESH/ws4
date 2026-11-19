# TSA24 active-spread and closed-line diagnostic

The raw incident out-dates include mop-up, so the previous duration test was not an
active-spread duration. This run instead uses consecutive fire-weather days until meaningful
rain or a seven-day cap. It also assumes the containment line is already closed when the fire
reaches it, so the only way a fire can exceed the target is an explicit escape.

## Result

Twelve training tiles, 10 fires each, 50 m cells, fire-danger-weighted weather.

| Statistic | Historical | Closed-line active-spread |
| --- | ---: | ---: |
| fires | 204 | 120 |
| mean | 258.2 ha | 49.3 ha |
| median | 21.7 ha | 35.0 ha |
| p90 | 267.0 ha | 163.8 ha |
| p95 | 809.7 ha | 184.6 ha |
| maximum | 11,394.6 ha | 199.3 ha |
| over 100 ha | 21.6% | 14.2% |
| over 500 ha | 6.9% | 0.0% |
| over 1,000 ha | 4.4% | 0.0% |

The closed-line assumption removes the runaway tail completely. The distribution is now
governed by the containment target:

- median too high at 35 ha
- p90 too low at 164 ha
- no fires above 500 ha

## Finding

Active-spread weather and closed-line containment are both necessary, but together they expose
the remaining missing process: **escape**. A closed line cannot produce the historical tail.
The escape must be explicit and conditioned on weather, active-spread duration, and fuel — not
a fixed random probability.

The next calibration should lower the containment median toward 20–25 ha and add a small,
weather-conditioned escape that supplies the 500–10,000 ha tail without a hard cap.

## Boundary

Twelve training tiles, 10 fires each, 50 m cells, one fire season of weighted weather. This is
a structural diagnostic, not a calibrated regime.
