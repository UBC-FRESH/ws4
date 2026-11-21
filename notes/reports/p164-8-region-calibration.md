# P164.8 regional fire-size calibration

Status: calibrated in-sample; no gate verdict

This is the usable regional calibration from the P164.8 potential sample. It replaces the
single global suppression fit with one parameter set per tile.

## Inputs

- 720 potential fires: 30 per tile, 24 tiles
- 10 active hours per day
- 90-day antecedent FWI spin-up
- VRI/SRTM/water layers
- historical perimeters clipped to each tile

## Method

For each tile with at least five historical fires:

- search 1,000 pre-registered-bounded parameter points
- simulate five realizations per potential fire
- minimize a weighted distribution distance over the 10th, 25th, 50th, 75th, 90th, and 95th
  percentiles
- weight over-500, over-1,000, and over-5,000 fractions
- store the best point per tile

No global pass/fail gate is applied.

## Aggregate result

| Statistic | Historical | Regional calibration |
| --- | ---: | ---: |
| fires | 432 | 3,450 |
| mean | 512.9 ha | 306.2 ha |
| median | 23.0 ha | 23.8 ha |
| p90 | 490.2 ha | 361.5 ha |
| p95 | 1,918.9 ha | 1,100.9 ha |
| over 100 ha | 26.2% | 23.6% |
| over 500 ha | 10.0% | 8.3% |
| over 1,000 ha | 7.9% | 5.5% |
| over 5,000 ha | 3.0% | 1.8% |
| maximum | 25,114.8 ha | 20,770.4 ha |

The central distribution and maximum are close. The upper-middle and extreme-tail fractions
remain low. The residual is reported, not hidden or converted into a gate.

## Parameters

Per-tile parameters are in:

`work/fire_regime/results/region-calibration.json`

Each entry records the contained fraction, escaped fraction, escape cap, hazard intercept,
training score, simulated metrics, and historical metrics for that tile.

## Boundary

This is an in-sample regional calibration: every tile's historical sample was used to choose
its parameters. There is no independent tile holdout claim. The sample uses one 2023 weather
season and 30 potential fires per tile. The residual tail underprediction is real and remains a
model limitation.

## Use

The regional parameter map is ready to be wired into `build_relative_fire_source` through its
region-config path. That is the next integration step; no further size-distribution gate work is
planned.
