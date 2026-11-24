# P164.9 size-dependent retention model

Phase identifier: P164
Task: P164.9
Status: active bounded move
Parent issue: #977
Task issue: #1436
Date: 2026-11-23

## Problem

The P164.8 relative-suppression model retained a fixed fraction of the potential fire size.
With the multi-year potential sample, several tiles collapsed to the 6.25 ha support minimum and
could not reproduce historical tile medians of 25--112 ha. The previous 2023-only fit had hidden
this structural limitation.

## Change

Added `ws4.fire.regime_retention` with:

- a log-normal contained-size distribution with a median at 1,000 ha potential;
- a contained-size exponent that allows weak or strong scaling with potential size;
- the existing escape hazard and escaped-fraction component;
- the existing absolute escape cap and minimum support area.

The contained component can now produce intermediate fire sizes without forcing every contained
fire to a fixed fraction of a large potential fire.

## Multi-year result

Inputs:

- Open-Meteo daily weather, 1950--2024, 24 tiles, 27,394 days each;
- 720 potential fires, year-stratified across 68 fire years;
- 30-day potential spread window;
- 23 tile maps, 1,000 candidates per tile, five draws per potential fire.

Pooled result (3,450 draws vs 432 historical fires):

| Metric | Historical | Retention model |
| --- | ---: | ---: |
| Median | 23.0 ha | 29.9 ha |
| p90 | 490.2 ha | 370.1 ha |
| p95 | 1,918.9 ha | 833.4 ha |
| Over 100 ha | 26.2% | 26.9% |
| Over 500 ha | 10.0% | 7.9% |
| Over 1,000 ha | 7.9% | 4.3% |
| Over 5,000 ha | 3.0% | 1.0% |
| Maximum | 25,114.8 ha | 24,147.1 ha |

Per-tile medians now reproduce the observed range in most tiles. The remaining failures are
informative: t07, t11, t13, t21, and t22 have modelled medians well above their historical medians,
while the upper tail remains low overall.

## What this establishes

The fixed-fraction model was structurally inadequate for the multi-year sample. The retention model
is a materially better process representation and should replace it for the calibration and fire
source.

## Integration result

The retention parameters are now wired into `RelativeSuppressionConfig` and the fire source. The
2026-11-24 reruns used the retention map:

- five-seed risk: median burned 4,463.6 ha; CVaR95 volume loss 1.167 million m3;
- five-year estate: 3,646.0 ha burned; 156,358.8 ha harvested; 822.1 million m3 final volume;
- feasibility search: 112 tiles, 179 entries, 652.7 ha burned in 91 events, 663.7 s; fire-blind
  schedule identical;
- pre-2018 retention map + 2018+ event holdout: median absolute bias 89.3%; the event test still
  fails;
- retention transfer: in-sample 1.337; potential analogue 4.456; training median 5.873; historical
  oracle 4.947.

## Not done

- transfer/event uncertainty intervals for the retention model;
- independent spatial validation;
- suppression-capacity covariates;
- paper claims have been updated to the multi-year retention calibration, but the event failure
  remains a boundary.

## Next bounded move

Bootstrap the retention transfer and event comparisons, then decide whether the event test belongs in
the paper or in a separate diagnostic note.

## Next bounded move

Wire the retention model into the fire-source interface, then refit the pre-2018 map and rerun the
temporal event holdout. Do not update the paper until those cases use the same retention model.
