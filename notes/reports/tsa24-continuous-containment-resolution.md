# TSA24 continuous containment calibration and resolution limit

The discrete three-tier sweep could not match the historical median and tail at the same time.
This run replaced the tiers with a continuous containment-area distribution conditioned on
duration and fire weather.

## Model

For each fire:

- sample duration and local 2023 FWI weather
- draw a lognormal target containment area
- condition the log-mean on duration, BUI, and wind
- place a containment ring at the equivalent radius
- sample line-closure time around 30 minutes
- allow a 5% uncapped escape tail

The first parameterization used a 20 ha median target and 1.45 log-sigma. The second used a
35 ha median and 1.15 log-sigma.

## Result

| Statistic | Historical | Continuous |
| --- | ---: | ---: |
| fires | 432 | 720 |
| mean | 512.9 ha | 1,275.5 ha |
| median | 23.0 ha | 6.3 ha |
| p90 | 490.2 ha | 460.0 ha |
| p95 | 1,918.9 ha | 8,599.4 ha |
| maximum | 25,114.8 ha | 60,006.3 ha |
| over 100 ha | 26.2% | 14.7% |
| over 500 ha | 10.0% | 9.7% |
| over 1,000 ha | 7.9% | 8.2% |
| over 5,000 ha | 3.0% | 5.7% |

The continuous model matches p90 and the over-500 and over-1,000 fractions, but it still
overproduces the extreme tail and cannot lower the median.

## Resolution finding

The 250 m grid cannot represent the historical median. A containment radius below roughly two
cells either leaves only the ignition cell (6.25 ha) or jumps to the next ring (about 50 ha).
The simulated median therefore sits at 6.25 ha while the historical median is 23 ha.

This is not a suppression-parameter problem. It is a fire-grid resolution problem.

## Required change

Run small-fire calibration on a finer fire grid, starting with a 50 m grid over a subset of the
24 tiles. The 250 m support map remains appropriate for block aggregation and full-estate
accounting; the fire-growth grid needs to be finer for the median.

## Boundary

The continuous run uses the same 720-fire sample, weather, and real VRI/SRTM layers. It is a
structural diagnostic, not a calibrated suppression model.
