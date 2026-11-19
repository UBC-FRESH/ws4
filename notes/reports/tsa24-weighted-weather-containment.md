# TSA24 weighted-weather containment calibration and held-out check

The random-weather 50 m runs were too suppressed, while constant hot weather overproduced the
tail. This test sampled weather days by fire danger instead, using the same 50 m grid and
continuous containment model.

## Method

- fire-danger weighting: `max(0, FWI - 5)^2` over the local 2023 fire-season days
- 50 m fire cells, upsampled from 250 m VRI/SRTM layers
- continuous containment target: 35 ha median, 0.85 log-sigma
- 2% uncapped escape
- containment target above 3,000 ha treated as an escape
- 20 fires per tile

Six tiles were used for calibration and six different tiles for validation.

## Calibration tiles

| Statistic | Historical | Calibrated |
| --- | ---: | ---: |
| fires | 87 | 120 |
| median | 15.6 ha | 14.9 ha |
| p90 | 229.0 ha | 237.1 ha |
| p95 | 555.1 ha | 399.7 ha |
| maximum | 10,602.2 ha | 22,577.8 ha |
| over 100 ha | 23.0% | 15.0% |
| over 500 ha | 5.7% | 5.0% |
| over 1,000 ha | 3.4% | 3.3% |

The calibration tiles fit the median, p90, over-500, and over-1,000 fractions closely.

## Held-out tiles

| Statistic | Historical | Held-out simulated |
| --- | ---: | ---: |
| fires | 123 | 120 |
| median | 28.2 ha | 16.3 ha |
| p90 | 275.4 ha | 754.8 ha |
| maximum | 11,394.6 ha | 40,064.0 ha |
| over 100 ha | 21.1% | 17.5% |
| over 500 ha | 6.5% | 13.3% |
| over 1,000 ha | 4.9% | 9.2% |

The held-out run overproduces the large-fire tail and lowers the median.

## Finding

Fire-danger weighting is the right weather-conditioning mechanism: it fixes the central
tendency on the calibration tiles. The current escape/containment parameters overfit those
tiles, however. The held-out large-fire fraction is roughly double the historical value, and
the maximum is almost four times larger.

The next calibration must use the held-out tiles in the objective and constrain the tail, not
just tune the six calibration tiles.

## Boundary

Six calibration and six validation tiles, 20 fires each. The 50 m layers are upsampled from
250 m data. The weights use one 2023 fire season, not historical fire-date weather. This is a
structural calibration diagnostic, not a finished suppression model.
