# TSA24 in-sample event reconstruction

Status: completed negative result; not independent

Date: 2026-11-23

## Question

Can the calibrated TSA24 fire regime reproduce independent observed fires from their incident ignition
points and event weather?

## Data and protocol

- Not independent: the 23-tile regional map was fitted on all tile histories; at least eight of the ten
event areas occur in those histories, and one event (G12186) is in a training tile.

- 247 independent fire perimeters ≥100 ha in the 24 fixed tiles.
- 18 events had matched incident records.
- 11 had complete ignition and out dates; one was outside the 100–20,000 ha selection range.
- 10 validation events were frozen before simulation.
- Point ignition from the BC Wildfire incident record.
- Event weather from Open-Meteo, including 90-day antecedent weather.
- Real VRI/SRTM/water layers at 250 m.
- Calibrated regional suppression map.
- One deterministic survival draw per event, seed `20261122`.
- Three records exceeded 90 days and were capped at 90 days; two are 420-day records inconsistent
  with the observed 2023 fires.
- No observed start perimeter; the validation is point ignition, not perimeter initiation.
- No event-specific tuning.

## Result

| Fire | Year | Observed (ha) | Simulated (ha) | Bias |
| --- | ---: | ---: | ---: | ---: |
| G41511 | 2023 | 4,767.8 | 1,556.2 | -67.4% |
| G41560 | 2023 | 1,144.3 | 1,656.2 | +44.7% |
| G41422 | 2023 | 780.0 | 487.5 | -37.5% |
| G40639 | 2018 | 327.3 | 806.2 | +146.3% |
| G41728 | 2021 | 309.4 | 568.8 | +83.8% |
| G40226 | 2019 | 236.0 | 250.0 | +5.9% |
| G51212 | 2021 | 151.7 | 1,112.5 | +633.4% |
| G40324 | 2023 | 142.7 | 4,656.2 | +3163.0% |
| G12186 | 2023 | 122.7 | 62.5 | -49.1% |
| G13085 | 2018 | 112.3 | 56.2 | -49.9% |

Summary:

- n = 10
- median bias: **+25.3%**
- median absolute bias: **58.6%**
- mean absolute bias: **428.1%**
- range: **-67.4% to +3163.0%**

## Interpretation

The result is a reconstruction, not a validation. It cannot establish transferable event-level skill.

The model fails independent event-level validation. The errors are large and bidirectional. The result is not a small calibration offset that can be
tuned away; it indicates that the current point-ignition growth/suppression configuration does not
reproduce observed event size.

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
`results/event-simulations-validation-90d.json`.
