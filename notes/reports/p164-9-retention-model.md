# P164.9 global retention model, temporal holdout, and applied cases

Phase identifier: P164
Task: P164.9
Status: active bounded move
Parent issue: #977
Task issue: #1436
Date: 2026-11-24

## Problem

The earlier P164.9 fit used tile-clipped fire records as if they were independent fires. A fire
spanning tiles appeared multiple times with a smaller area, and per-tile seven-parameter fits were
underdetermined. The applied risk/estate/optimizer cases also used a private sigma mapping and a
seven-cell ignition design.

## Change

The canonical history now aggregates tile clips by fire number and year. That yields 361 unique
fires; 267 are at or above the 6.25 ha raster floor and form the global target. The 24 potential
tiles contribute 720 potential fires; five draws per potential fire give 3,600 correlated
realizations. One global seven-parameter retention distribution is fitted with 5,000 candidates and
common random numbers. A spanning fire is assigned to its largest clipped tile only for per-tile
residual diagnostics.

The model is a fitted two-component retention/escape distribution, not a resource-allocation
suppression mechanism. A retained draw is capped at the potential fire; the maximum is not
interpreted.

## Calibration result

Pooled unique-fire result:

| Metric | Historical | Global retention model |
| --- | ---: | ---: |
| Median | 64.2 ha | 65.6 ha |
| p90 | 1,497.2 ha | 1,575.6 ha |
| p95 | 4,625.2 ha | 5,661.0 ha |
| Over 100 ha | 40.8% | 43.2% |
| Over 500 ha | 15.7% | 20.1% |
| Over 1,000 ha | 12.4% | 13.3% |
| Over 5,000 ha | 4.9% | 5.4% |

This is a strong in-sample fit. The over-500 fraction is high; the maximum is not interpreted.

## Historical trend and temporal holdout

The empirical record shows a clear post-2017 shift in annual area and the upper tail. Unique-fire
annual area is about 1,736 ha/year in 1950--2016, 25,959 ha in 2017, and 11,327 ha/year in
2018--2024. The share of unique fires above 5,000 ha rises from 2.3% to 6.2%, and the p90 of fires
at or above 6.25 ha rises from 698 ha to 4,768 ha.

The pre-2018 model is fit on 218 unique fires and 608 potential records, then tested once on 49
unique fires and 74 potential records from 2018--2024:

| Period | Metric | Historical | Model |
| --- | --- | ---: | ---: |
| Pre-2018 fit | Median | 56.6 ha | 57.0 ha |
| Pre-2018 fit | p90 | 886.9 ha | 946.1 ha |
| 2018--2024 | Median | 142.7 ha | 36.6 ha |
| 2018--2024 | p90 | 5,729.0 ha | 1,119.4 ha |
| 2018--2024 | Over 5,000 | 10.2% | 1.6% |

The temporal holdout fails. The 2018+ distribution is shifted upward and the pre-2018 parameters do
not carry forward. A cutoff at 2017 gives the same conclusion.

## Transfer result

Training: 12 tiles; validation: 11 tiles; `t24` has no historical record.

| Method | Mean score (95% CI) | Median |
| --- | ---: | ---: |
| In-sample global map | 5.404 (3.810--7.116) | 5.670 |
| Historical-feature oracle | 4.805 (3.283--6.335) | 4.957 |
| Potential/weather analogue | 4.579 (3.197--6.075) | 4.737 |
| Global fit, 12 training tiles | 5.595 (4.190--7.059) | 5.908 |

Global-minus-potential: +1.016 with 95% interval [-0.727, 2.724]. The global model is stable between
in-sample and training-only evaluation, but it does not beat the potential analogue. This is a null
transfer result, not per-tile overfitting.

## Applied cases

`contained_sigma` now maps to the applied `contained_fraction_sigma`; the public loaders accept the
retention schema and the full-layer manifest. Risk, estate, and optimizer cases were rerun on the
unique-fire global map with 15 fixed ignitions sampled without replacement from all burnable cells:

- five-seed suppression-draw risk: median burned 7,478.8 ha; volume loss 0.569--1.384 million m3;
  worst-of-five 1.384 million m3;
- five-year estate: 565 fragment-level events, 5,842.3 ha burned, 156,358.8 ha harvested,
  821.7 million m3 final volume;
- feasibility search: 112 tiles, 179 entries, 661.0 ha burned in 72 events, 655.2 s; the fire-blind
  schedule is invariant because fire does not enter the harvest-area objective.

## Not done

- estate-wide ignition/weather ensemble (running);
- independent spatial validation and a TSA24 external benchmark;
- suppression-capacity covariates;
- clean-host raw-to-result rerun;
- public archive, DOI, and licence sign-off.

## Next bounded move

Finish the estate-wide ensemble and external benchmark, then rerun a fresh adversarial review. Do
not submit until the temporal failure and null transfer are either accepted as the paper's boundary
or addressed by a model with climate/time covariates.
