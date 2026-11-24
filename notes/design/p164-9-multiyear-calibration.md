# P164.9 multi-year weather calibration

Phase identifier: P164
Status: active
Parent issue: #977
Working branches: `manuscript/p164-paper1-draft` (paper) and `main` (reproduction archive)
Date: 2026-11-24

## Goal

Replace the 2023-only potential-fire weather sample with a multi-year weather sample and fit a
retention model on historical fires that the 250 m grid can represent.

## Why

The original potential sample used one 2023 weather season while historical perimeters span
1950--2024. That is not a multi-year calibration. Open-Meteo historical weather is available for
1950--2024; the limitation was the pipeline, not the data. The original historical target also
included fires below the 6.25 ha raster floor, so the comparison was not like-for-like.

## Inputs

- Open-Meteo archive daily weather, 1950-01-01 to 2024-12-31, 24 tiles, 27,394 days each.
- VRI/SRTM/water layer cache.
- Historical BC Wildfire perimeters, 1950--2024, clipped to tile boundaries.
- Fixed tile split: `t01`--`t12` train, `t13`--`t23` validation; `t24` excluded.
- 30 potential fires per tile, fire-danger-weighted starts with replacement.
- 30-day maximum potential-fire spread window, stopped by 2 mm precipitation.
- Five draws per potential fire for calibration metrics.

## Sequence

1. Fetch and hash the 24 multi-year weather files.
2. Build `results/potential-multiyear`.
3. Fit `results/region-retention-multiyear-all.json` on historical records at or above 6.25 ha.
4. Summarize pooled residuals and build Figure 3 from the same map.
5. Fit a transfer comparison on training tiles only, including a global fit and bootstrap intervals.
6. Rerun risk, five-year estate, and feasibility cases on the same map.
7. Regenerate figures, manifest, and paper tables.
8. Run a fresh review before submission.

The event reconstruction is not part of this sequence. The earlier shared-draw event experiment is
a documented failure-mode diagnostic, not a holdout.

## Acceptance

- Twenty-four weather files, with SHA-256 in `INPUT_MANIFEST.sha256`.
- 720 potential fires across 68 fire years; start-year distribution recorded.
- A 20-tile retention map fitted only on fires >=6.25 ha; 299 representable records reported.
- Transfer comparison with global fit, training median, potential analogue, historical-feature
  oracle, and tile-bootstrap intervals.
- Risk/estate/feasibility cases rerun on the same map with the applied sigma mapped correctly.
- One canonical manifest and one paper table set.
- Dashboard and archive verification green.
- Fresh adversarial review completed.

## Stop conditions

- If the multi-year fit materially worsens the central distribution, treat that as evidence that the
  retention formulation or weather driver is inadequate; do not revert to 2023 to make the paper
  look better.
- Do not submit until the fresh review passes.
- Do not add new engineering thresholds or call them scientific evidence.
