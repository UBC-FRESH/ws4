# P164.9 multi-year weather calibration

Phase identifier: P164
Status: active
Parent issue: #977
Working branches: `manuscript/p164-paper1-draft` (paper) and
`main` (reproduction archive)
Date: 2026-11-23

## Goal

Replace the 2023-only potential-fire weather sample with a multi-year weather sample and refit the
TSA24 fire regime. This is the decisive test of whether the current regional calibration is a
weather-year fit or a multi-year calibration.

## Why

The current potential sample is generated under one 2023 weather season, while the historical
perimeters span 1950--2024. That is not a multi-year calibration. Open-Meteo historical weather is
available for 1950--2024; the limitation is the pipeline, not the data.

## Inputs

- Open-Meteo archive daily weather, 1950-01-01 to 2024-12-31, 24 tiles.
- VRI/SRTM/water layer cache.
- Historical BC Wildfire perimeters, 1950--2024.
- Fixed tile split: `t01`--`t12` train, `t13`--`t23` validation.
- 30 potential fires per tile, year-stratified starts.
- 30-day maximum potential-fire spread window, stopped by 2 mm precipitation.
- Five realizations per potential fire for calibration metrics.

## Sequence

1. Fetch and verify 24 multi-year weather files.
2. Build `results/potential-multiyear`.
3. Fit `results/region-calibration-multiyear-all.json` on all historical fires.
4. Summarize pooled residuals and compare with the 2023 fit.
5. Fit `results/region-calibration-pre2018.json` on fires before 2018.
6. Run training-only transfer and ridge diagnostics on the all-history map.
7. Run the event reconstruction on the pre-2018 map, so 2018+ events are temporal holdout.
8. Rerun risk, five-year estate, and feasibility cases on the all-history map.
9. Rerun bootstrap intervals and regenerate figures.
10. Update the paper and archive from the canonical multi-year run.

## Acceptance

- Twenty-four weather files, 27,394 daily records each, with SHA-256 hashes.
- Seven hundred twenty potential fires across multiple years; start-year distribution recorded.
- A 23-tile multi-year map; pooled calibration residuals reported, not hidden.
- A pre-2018 map and a genuinely temporal event reconstruction.
- Transfer and ridge results on one map, not mixed artifacts.
- Risk/estate/feasibility cases rerun on the same map.
- One canonical manifest and one paper table set.
- Dashboard and archive verification green.

## Stop conditions

- If the multi-year fit materially worsens the central distribution, treat that as evidence that the
  suppression formulation or weather driver is inadequate; do not revert to 2023 to make the paper
  look better.
- Do not submit the general paper until this task is complete.
- Do not add new engineering thresholds or call them scientific evidence.
