# P164.8 hierarchical/partial-pooling transfer test

Status: diagnostic

This run tests whether a partial-pooling model can transfer suppression parameters to the
held-out `t13`–`t23` tiles. It follows the independent transfer test in
`notes/reports/p164-8-transfer-validation.md`.

## Model

Six parameters were modelled separately:

- contained fraction median, log scale
- contained fraction log-sigma, log scale
- escaped fraction median, log scale
- escaped fraction log-sigma, log scale
- escape cap, log scale
- escape intercept, identity scale

The predictor matrix used only information available for a new tile:

- log median potential fire size
- log p90 potential fire size
- log mean potential fire size
- mean FWI
- mean BUI
- mean wind speed
- mean active-spread days

The model is an empirical-Bayes ridge regression with an unpenalised intercept. Features were
standardised on the 12 training tiles. Shrinkage was selected by leave-one-tile-out on the training
split using the actual suppression simulation score, not parameter-space error. Predictions were
clipped to the pre-registered P164.8 bounds.

## Selection

Lambda grid: `0.01, 0.03, 0.1, 0.3, 1, 3, 10, 30, 100`.

The training leave-one-tile-out scores were:

| Lambda | Mean score |
| ---: | ---: |
| 100 | **4.731** |
| 30 | 4.778 |
| 10 | 4.958 |
| 3 | 5.079 |
| 1 | 5.489 |
| 0.3 | 5.849 |
| 0.1 | 6.288 |
| 0.03 | 6.961 |
| 0.01 | 7.191 |

Lambda `100` was selected. The fitted model was then frozen and applied once to the validation
tiles.

## Validation result

| Method | Mean score | Median score | Median log error | p90 log error | Over-500 error | Over-1,000 error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `in_sample` | **1.495** | **1.478** | **0.296** | **0.194** | **0.027** | **0.011** |
| `partial_pool_mean` | 5.182 | 4.994 | 0.577 | 1.583 | 0.060 | 0.061 |
| `global` | 5.287 | 5.082 | 0.903 | 1.310 | 0.097 | 0.053 |
| `hierarchical_ridge` | 6.540 | 7.219 | 1.776 | 1.737 | 0.140 | 0.090 |

Lower is better. Validation tiles: `t13`–`t23`; `t24` is excluded.

## Finding

The partial-pooling covariates did not recover transferable regional skill. The ridge model was
selected by training-only simulation score but performed worse than both complete pooling and the
global fit on the held-out tiles. The simple pool mean was the most robust transfer estimator.

The likely reasons are:

- only 12 training tiles for six parameters and seven predictors;
- the suppression parameters are weakly identified from potential growth and weather alone;
- the training and validation tile distributions differ;
- the parameter-space and simulation-space objectives are not aligned;
- the per-tile parameter estimates are themselves noisy.

This is a negative result for this covariate set, not proof that no hierarchical model can work.
A future model needs stronger covariates: suppression capacity, response time, access, fire
management policy, multi-year weather, and observed active-spread duration.

## Boundary

- 11 validation tiles; one 2023 weather season; 30 potential fires per tile.
- The score is a diagnostic, not the pre-registered P164.8 gate.
- No validation-tile parameter tuning.
- The model predicts suppression parameters, not observed fire behaviour.
- The result does not establish that regional calibration is useless; it establishes that the
  current regional fits are in-sample descriptions, not transferable predictions.

## Artifact

`work/fire_regime/results/hierarchical-validation-simcv.json`
