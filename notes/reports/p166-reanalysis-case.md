# P166 CFSDS hourly-reanalysis case

Date: 2026-11-11
Phase: P166 (#991)
Task: P166.2 (#993)
Case: CFSDS `2003_526`
Fixture: `tests/fixtures/fire/cfsds_2003_526`
Metrics: `notes/reports/p166-reanalysis-case.json`

## Case

- Event: 2003-08-20 13:00 to 2003-09-04 23:00 local.
- Final observed scar: 520 ha from CFSDS `2003_526_krig.tif`.
- Grid: 90 x 76 cells at 100 m, EPSG:26911.
- Fuel/terrain: FireSTARR Fuel 2023 V1.0 tile 11_0.
- Weather: Open-Meteo hourly reanalysis at the reconstructed ignition.
- Ignition: centroid of the first-day burned cells.
- Starting codes: FFMC 90.83, BUI 74.12 from the CFSDS event day.

This is an independent CFSDS event, but it is **depth-with-limit**:

- hourly weather is reanalysis, not an on-site station;
- perimeters are daily satellite-derived snapshots;
- ignition is reconstructed.

## Uncalibrated result

| Metric | Value |
| --- | ---: |
| Simulated area | 5,325 ha |
| Observed area | 520 ha |
| Area bias | +924% |
| Perimeter bias | +496% |
| IoU | 0.096 |
| Sorensen | 0.175 |
| Centroid distance | 175 m |
| Orientation error | 21.6° |

The model badly overpredicts area and perimeter. The centroid is close, so the failure is
scale and shape, not gross displacement.

## Decision

P166 adds one independent depth-with-limit case, not a fully ready depth case. The uncalibrated
result is recorded as a failure. No multiplier, fuel tweak, or weather adjustment was applied.

P164.3 calibration remains paused. This case is a baseline target for later work, not evidence
that the model is calibrated.
