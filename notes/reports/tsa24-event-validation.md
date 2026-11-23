# TSA24 independent event validation

Status: completed negative result

Date: 2026-11-23

## Question

Can the calibrated TSA24 fire regime reproduce independent observed fires from their incident ignition
points and event weather?

## Data and protocol

- 247 independent fire perimeters ≥100 ha in the 24 fixed tiles.
- 18 events had matched incident records.
- 11 had complete ignition and out dates; one was outside the 100–20,000 ha selection range.
- 10 validation events were frozen before simulation.
- Point ignition from the BC Wildfire incident record.
- Event weather from Open-Meteo, including 90-day antecedent weather.
- Real VRI/SRTM/water layers at 250 m.
- Calibrated regional suppression map.
- One deterministic survival draw per event, seed `20261122`.
- No observed start perimeter; the validation is point ignition, not perimeter initiation.
- No event-specific tuning.

## Result

| Fire | Year | Observed (ha) | Simulated (ha) | Bias |
| --- | ---: | ---: | ---: | ---: |
| G41511 | 2023 | 4,767.8 | 887.5 | -81.4% |
| G41560 | 2023 | 1,144.3 | 550.0 | -51.9% |
| G41422 | 2023 | 780.0 | 268.8 | -65.5% |
| G40639 | 2018 | 327.3 | 50.0 | -84.7% |
| G41728 | 2021 | 309.4 | 481.2 | +55.5% |
| G40226 | 2019 | 236.0 | 112.5 | -52.3% |
| G51212 | 2021 | 151.7 | 625.0 | +312.0% |
| G40324 | 2023 | 142.7 | 987.5 | +592.0% |
| G12186 | 2023 | 122.7 | 6.2 | -94.9% |
| G13085 | 2018 | 112.3 | 50.0 | -55.5% |

Summary:

- n = 10
- median bias: **-53.9%**
- median absolute bias: **73.5%**
- mean absolute bias: **144.6%**
- range: **-94.9% to +592.0%**

## Interpretation

The model fails independent event-level validation. The errors are large and bidirectional. The
result is not a small calibration offset that can be tuned away; it indicates that the current
point-ignition growth/suppression configuration does not reproduce observed event size.

The failure is consistent with the earlier negative transfer result. It also reinforces that the
in-sample fire-size fit is not evidence of event-level skill.

## What this does not test

- observed start-perimeter initiation;
- hourly fire-perimeter progression;
- suppression resources or tactics;
- external-model performance on the same events;
- multiple survival draws or parameter uncertainty.

The next test must be an external benchmark and a spatial perimeter comparison on the same events.
Until then, no operational or validated-forecast claim is permitted.

## Artifact

`https://github.com/UBC-FRESH/fresh_ws4_fire_regime_repro` (private):
`results/event-simulations-validation.json`.
