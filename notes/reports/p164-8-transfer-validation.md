# P164.8 regional suppression transfer validation

Status: independent transfer diagnostic

This run tests whether the per-tile suppression parameters in
`work/fire_regime/results/region-calibration.json` transfer to held-out tiles. It does not tune
parameters on the validation tiles.

## Design

- fixed split from `scripts/fire_regime/tiles.json`
- training tiles: `t01`–`t12`
- validation tiles: `t13`–`t23`; `t24` has no historical perimeter sample
- 30 potential fires per tile from the 10-hour, 90-day-antecedent sample
- five deterministic suppression draws per potential fire, giving 150 simulated fires per tile
- historical metrics from the per-tile clipped perimeter sample
- validation parameters were frozen before evaluation

Methods compared:

| Method | Parameter source |
| --- | --- |
| `global` | best global training fit from the P164.8 no-go run |
| `train_median` | median of the 12 training tile parameter sets |
| `potential_analogue` | nearest training tile by potential-growth and weather features |
| `historical_analogue` | nearest training tile by historical fire-size features; oracle diagnostic |
| `in_sample` | each tile's own fitted parameters; upper bound, not a transfer test |

The transfer score is a normalized distance to the tile's historical metrics: log median, log p90,
log p95, over-500, over-1,000, over-5,000, and log maximum. Lower is better.

## Results

| Method | Mean score | Median score | Median log error | p90 log error | Over-500 error | Over-1,000 error | Over-5,000 error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `in_sample` | **1.495** | **1.478** | **0.296** | **0.194** | **0.027** | **0.011** | **0.004** |
| `historical_analogue` (oracle) | 3.426 | 3.486 | 1.377 | 0.558 | 0.050 | 0.031 | 0.005 |
| `train_median` | 4.680 | 5.088 | 0.949 | 0.770 | 0.021 | 0.050 | 0.020 |
| `global` | 4.799 | 3.948 | 0.763 | 1.318 | 0.065 | 0.070 | 0.030 |
| `potential_analogue` | 6.121 | 5.944 | 0.959 | 1.574 | 0.085 | 0.079 | 0.020 |

The nearest-potential donor was usually `t03` or `t04`:

- `t13`, `t14`, `t15`, `t18`, `t19`, `t22`, `t23` → `t03`
- `t16` → `t07`
- `t17` → `t02`
- `t20`, `t21` → `t04`

## Finding

The in-sample regional fit is much closer to the historical tile metrics than any transfer method.
That is expected, but it means the in-sample residual table overstates regional skill.

The deployable potential/weather analogue performs worse than the global fit and the training
median. Potential-growth and weather features do not identify the suppression regime. Even the
oracle historical analogue remains well above the in-sample score. The current per-tile parameters
are not transferable with the available covariates.

This does not show that regional calibration is useless. It shows that independent regional
calibration is a fit, not a predictive model. A transferable model needs either:

- hierarchical/partial pooling of the six suppression parameters across tiles;
- explicit covariates for suppression capacity, access, response, and fire management;
- multi-year weather and duration data, rather than one 2023 season;
- a spatial or temporal holdout that is not used to choose the regional structure.

## Boundary

- 11 validation tiles, one 2023 weather season, 30 potential fires per tile.
- The score is a diagnostic, not the pre-registered P164.8 gate.
- The historical analogue uses validation historical metrics to choose the donor; it is an oracle,
  not a deployable method.
- The validation sample has no raw historical pooling across tiles in this analysis.
- No parameters were tuned on validation tiles.

## Artifact

`work/fire_regime/results/transfer-validation.json`
