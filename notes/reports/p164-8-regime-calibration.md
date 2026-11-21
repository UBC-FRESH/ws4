# P164.8 regime calibration result

Status: closed as **no-go**

Protocol: `notes/design/ws4-regime-calibration-protocol.md`

Task: #1421

## Run

- fixed 24-tile split: `t01–t12` train, `t13–t24` validation (`t24` has no historical fires)
- 30 potential fires per tile, 720 total
- 10 active spread hours per day
- 90-day antecedent FWI spin-up
- 1,500 pre-registered candidates
- training-only selection, then one validation evaluation

Sample manifest:

- seed: `20261121`
- train SHA-256: `411adf12ca6ff03ab1d3fff8a244e0dd0b375d6f1f8ed2e366cf8adc573aac9e`
- validation SHA-256: `01bd9ab71efae27d8d0b86726a240bcda7a4b9863b2aaa5efd10e50d0935e19d`

## Best training candidate

- contained fraction median: `0.002054`, log-sigma `1.382`
- escaped fraction median: `0.06031`, log-sigma `0.503`
- escape cap: `26,727 ha`
- escape intercept: `-3.180`

## Metrics

| Metric | Training | Training gate | Validation | Validation gate |
| --- | ---: | --- | ---: | --- |
| median | 28.37 ha | pass | 23.35 ha | pass |
| p90 | 493.11 ha | pass | 793.28 ha | **fail** |
| p95 | 1,534.64 ha | report | 1,652.29 ha | report |
| over 100 ha | 26.94% | pass | 25.56% | pass |
| over 500 ha | 10.00% | pass | 11.94% | pass |
| over 1,000 ha | 5.83% | pass | 7.78% | pass |
| over 5,000 ha | 0.56% | **fail** | 1.39% | pass |
| maximum | 6,059.03 ha | **fail** | 9,474.34 ha | **fail** |

## Verdict

**No-go.** The training sample fails the maximum and over-5,000 gates, so no candidate can be
promoted under the protocol. The validation sample additionally fails p90 and maximum.

No parameter was tuned on the validation tiles. The gate-aware training search found no
candidate that passes all training gates; the reported candidate is the best training score,
not a supported fit.

## Boundary

The sample uses one 2023 weather season, fire-danger-weighted start dates, and a 10-hour active
day. The historical comparison uses perimeters clipped to 30 km tiles. The potential-growth
model can reach the observed tail in individual tail-event audits, but the fixed 30-fire tile
sample does not produce a gate-passing distribution.

## Next decision

Do not continue parameter sweeps under P164.8. A new hypothesis or data source is required:
multi-year weather, observed active-spread durations, or a different large-fire event
formulation. That is a separate protocol change.
