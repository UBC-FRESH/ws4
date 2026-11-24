# P164.9 global retention model and corrected applied cases

Phase identifier: P164
Task: P164.9
Status: active bounded move
Parent issue: #977
Task issue: #1436
Date: 2026-11-24

## Problem

The earlier P164.9 retention fit used one seven-parameter set per tile. Several tiles had only five
to seven representable historical records, so those fits were underdetermined and the pooled tail
was weak. The applied risk/estate/optimizer cases also used a private sigma mapping and a
seven-cell ignition design.

## Change

Added `ws4.fire.regime_retention` as a size-dependent two-component retention/escape distribution.
The retained component is a log-normal size distribution with a weak potential-size exponent; the
escaped component is a log-normal fraction of potential, capped by a fitted escape area. The
retained draw is capped at the potential fire. This is a fitted size distribution, not a
resource-allocation suppression model.

The canonical calibration is now one global seven-parameter fit on the pooled representable sample:

- Open-Meteo daily weather, 1950--2024, 24 tiles, 27,394 days each;
- 720 potential fires, fire-danger-weighted across 68 fire years;
- 30-day potential spread window;
- 23 tiles with representable historical records;
- 311 tile-clipped historical records at or above the 6.25 ha floor;
- 690 potential fires in those tiles;
- five draws per potential fire = 3,450 correlated realizations;
- 1,000 candidates, seed 20261121.

The per-tile map remains a diagnostic, not the primary model. A seven-parameter fit to five to seven
records is not an identified process estimate.

## Calibration result

Pooled result (3,450 draws vs 311 historical records):

| Metric | Historical | Global retention model |
| --- | ---: | ---: |
| Median | 54.4 ha | 49.7 ha |
| p90 | 1,345.2 ha | 1,238.7 ha |
| p95 | 2,683.3 ha | 2,655.5 ha |
| Over 100 ha | 36.3% | 39.6% |
| Over 500 ha | 13.8% | 18.6% |
| Over 1,000 ha | 10.9% | 11.8% |
| Over 5,000 ha | 4.2% | 2.8% |

The maximum is not interpreted: a retained draw can reach the full potential fire. The global model
is strong in the centre and upper quantiles; it overproduces the over-500 fraction and
underproduces the over-5,000 fraction.

## Transfer result

Training split: all 12 tiles `t01`--`t12`; validation: 11 tiles `t13`--`t23`; `t24` is excluded.
The global model can use the sparse training tiles because it has one parameter set.

| Method | Mean score (95% CI) | Median |
| --- | ---: | ---: |
| In-sample global map | 5.158 (3.865--6.480) | 4.933 |
| Historical-feature oracle | 4.701 (3.396--5.997) | 4.296 |
| Potential/weather analogue | 4.712 (3.541--6.028) | 4.061 |
| Global fit, training tiles only | 5.261 (4.002--6.491) | 5.685 |

Global-minus-potential: +0.549 with 95% interval [-0.569, 1.696]. The global model is stable
between in-sample (5.158) and training-only (5.261) evaluation, but it does not beat the potential
analogue. This is a null transfer result, not a collapse or evidence of per-tile overfitting.

## Applied cases

The correction maps `contained_sigma` into the applied `contained_fraction_sigma`; the public
`load_calibrated_regions` accepts the retention schema; `load_estate_grid` resolves the archive
layer directory. Tests cover the schema, applied-draw equivalence, retained-area cap, escape cap,
and layer-path fallback.

The risk, estate, and optimizer cases were rerun on the global map with 15 fixed ignitions sampled
uniformly without replacement from all burnable support cells (three per year):

- five-seed suppression-draw risk: median burned 4,647.1 ha; volume loss 0.643--1.271 million m3;
  worst-of-five 1.271 million m3;
- five-year estate: 462 fragment-level events, 4,067.3 ha burned, 156,358.8 ha harvested,
  821.9 million m3 final volume;
- feasibility search: 112 tiles, 179 entries, 925.3 ha burned in 97 events, 501.2 s; the fire-blind
  schedule is invariant because fire does not enter the harvest-area objective.

The 15 ignitions are a fixed sample, not an estate-wide fire regime; they are now spread across the
estate rather than confined to seven candidate tiles.

## Events

The event reconstruction is not in the paper. The original event runs shared the same first random
draw, so no event escaped; the applied sigma was also wrong. The archive retains the event JSON as a
failure-mode diagnostic only. It is not a temporal holdout and not a model-skill result.

## Not done

- independent temporal validation with validation years excluded from the fit;
- an estate-wide stochastic ignition/weather ensemble;
- suppression-capacity covariates;
- deployable historical-analogue method;
- clean-host raw-to-result rerun;
- public archive, DOI, and licence sign-off.

## Next bounded move

Run a fresh adversarial review of the global calibration and null transfer result. Do not submit
until the review passes. The next scientific step is an independent temporal/spatial validation with
the validation years excluded from the fit, not another in-sample refit.
