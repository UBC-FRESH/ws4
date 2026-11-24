# P164.9 size-dependent retention model

Phase identifier: P164
Task: P164.9
Status: active bounded move
Parent issue: #977
Task issue: #1436
Date: 2026-11-24

## Problem

The P164.8 relative-suppression model retained a fixed fraction of the potential fire size.
With the multi-year potential sample, several tiles collapsed to the 6.25 ha support minimum and
could not reproduce historical tile medians of 25--112 ha. The previous 2023-only fit had hidden
this structural limitation.

## Change

Added `ws4.fire.regime_retention` with:

- a log-normal retained-size distribution with a median at 1,000 ha potential;
- a retained-size exponent that allows weak or strong scaling with potential size;
- the existing escape hazard and escaped-fraction component;
- the existing absolute escape cap and minimum support area.

The retained component can produce intermediate fire sizes without forcing every retained fire to a
fixed fraction of a large potential fire. A retained draw above the potential area is capped at the
potential area. The model is a two-component size distribution, not a resource-allocation
suppression model. The simulated maximum is not interpreted: a retained draw can reach the full
potential fire. The escape cap bounds only the escaped component.

## Applied-model correction

The calibration JSON uses `contained_sigma`; the applied `RelativeSuppressionConfig` uses
`contained_fraction_sigma`. The applied loaders now map `contained_sigma` into that field, and
`ws4.ecosystem.estate_fire.load_calibrated_regions` accepts the retention schema. Previously every
applied case silently used the 0.8 default. The risk, estate, and optimizer cases were rerun after
the correction. Tests cover the public loader, the applied draw against `draw_retention`, the
retained-area cap, and the escape cap.

## Multi-year result

Inputs:

- Open-Meteo daily weather, 1950--2024, 24 tiles, 27,394 days each;
- 720 potential fires, fire-danger-weighted across 68 fire years;
- 30-day potential spread window;
- 20 tile maps with at least five historical records at or above the 6.25 ha floor;
- 600 potential fires, 1,000 candidates per tile, five draws per potential fire.

Calibration target: 299 tile-clipped historical records at or above 6.25 ha. The 432-record product
contains 121 sub-resolution records; those cannot be represented on the 250 m grid and were excluded
from the like-for-like comparison. Records are tile-fire records, not independent fires.

Pooled result (3,000 draws vs 299 historical records):

| Metric | Historical | Retention model |
| --- | ---: | ---: |
| Median | 55.9 ha | 59.5 ha |
| p90 | 1,013.2 ha | 483.0 ha |
| p95 | 2,607.0 ha | 997.7 ha |
| Over 100 ha | 36.1% | 37.5% |
| Over 500 ha | 13.0% | 9.9% |
| Over 1,000 ha | 10.0% | 5.0% |
| Over 5,000 ha | 4.0% | 1.3% |

Per-tile fits range from five to seven records in several tiles; those fits are descriptive, not
identified process estimates. The pooled central fit is good; the upper tail remains low. The
pooled maximum is not reported because a retained draw can reach the full potential fire.

## Transfer result

Training split: nine tiles with a fitted map (`t07`, `t08`, and `t11` have fewer than five
representable records). Validation: 11 tiles (`t13`--`t23`). The transfer score uses historical
records at or above 6.25 ha and a 10,000-resample tile bootstrap.

| Method | Mean score (95% CI) | Median |
| --- | ---: | ---: |
| In-sample regional fit | 1.102 (0.856--1.360) | 1.093 |
| Historical-feature oracle | 3.079 (2.288--3.900) | 2.952 |
| Global fit | 6.041 (4.423--7.721) | 6.171 |
| Potential/weather analogue | 6.240 (4.778--7.961) | 5.417 |
| Training median | 7.107 (5.059--9.226) | 7.990 |

The global fit is the best non-oracle method by point estimate, but global-minus-potential is
-0.199 with a 95% interval of [-1.666, 1.460], so the ranking is unresolved. The historical-feature
oracle is not deployable; its lower score shows that fire-size history carries information that
potential growth and weather do not.

## Integration result

The corrected retention map was used for:

- five-seed suppression-draw risk case: median burned 10,215.2 ha; volume loss 0.847--1.716 million
  m3; worst-of-five 1.716 million m3. Ignitions and weather are fixed; only the suppression draw
  varies;
- five-year estate case: 939 fragment-level events, 8,062.2 ha burned, 156,358.8 ha harvested,
  821.6 million m3 final volume;
- feasibility search: 112 tiles, 179 entries, 1,452.5 ha burned in 191 events, 735.5 s; the
  fire-blind schedule is invariant because fire does not enter the harvest-area objective.

## Events

The event reconstruction is not in the paper. The original event runs shared the same first random
draw, so no event escaped; the applied sigma was also wrong. Those defects are documented in the
review and in the archive. The archive retains the event JSON as a failure-mode diagnostic only. It
is not a temporal holdout and not a model-skill result.

## Not done

- independent spatial validation;
- suppression-capacity covariates;
- hierarchical or regularised estimation for tiles with five to seven records;
- a deployable historical-analogue method that does not use the target tile's history;
- clean-host raw-to-result rerun;
- public archive, DOI, and licence sign-off.

## Next bounded move

Run a fresh adversarial review of the corrected paper and archive. Do not submit until the review
passes. The next scientific step is an independent temporal/spatial validation with the validation
years excluded from the fit, not another in-sample refit.
