# P164.9 multi-year global retention calibration

Phase identifier: P164
Status: active
Parent issue: #977
Working branches: `manuscript/p164-paper1-draft` (paper) and
`main` (reproduction archive)
Date: 2026-11-24

## Goal

Fit a multi-year retention model on historical fires that the 250 m grid can represent, without
pretending that seven parameters are identified separately in tiles with five historical records.

## Why

The 2023-only potential sample was not a multi-year calibration. The original historical target also
included fires below the 6.25 ha raster floor. Per-tile seven-parameter fits were underdetermined.
The canonical model is therefore one global retention parameter set fitted to the pooled
representable sample; per-tile residuals remain descriptive diagnostics.

## Inputs

- Open-Meteo archive daily weather, 1950-01-01 to 2024-12-31, 24 tiles, 27,394 days each.
- VRI/SRTM/water layer cache.
- Historical BC Wildfire perimeters, 1950--2024, clipped to tile boundaries.
- Fixed split: `t01`--`t12` train, `t13`--`t23` validation; `t24` excluded.
- 30 potential fires per tile, fire-danger-weighted starts with replacement.
- 30-day maximum potential spread window, stopped by 2 mm precipitation.
- Five draws per potential fire.
- Historical target restricted to fires at or above 6.25 ha.

## Sequence

1. Fetch and hash the 24 multi-year weather files.
2. Build `results/potential-multiyear`.
3. Fit `results/region-retention-global-all.json` on the pooled representable sample.
4. Summarize `results/region-retention-global-summary.json` and build Figure 3.
5. Fit the 12-training-tile transfer comparison with a global fit, potential analogue, historical
   oracle, and bootstrap intervals.
6. Rerun risk, five-year estate, and feasibility cases on the global map with estate-wide fixed
   ignitions.
7. Regenerate figures, manifest, and paper tables.
8. Run a fresh review before submission.

The event reconstruction is not part of this sequence. The earlier shared-draw event experiment is a
documented failure-mode diagnostic, not a holdout.

## Acceptance

- Twenty-four weather files, with SHA-256 in `INPUT_MANIFEST.sha256`.
- 720 potential fires across 68 fire years.
- One global seven-parameter model fitted on 311 representable records in 23 tiles.
- 3,450 draws reported, not presented as independent fires.
- Transfer comparison with global fit, potential analogue, historical-feature oracle, and
  tile-bootstrap intervals.
- Risk/estate/optimizer cases rerun on the same global map with 15 estate-wide fixed ignitions.
- One canonical manifest and one paper table set.
- Archive verification, paper CI, and WS4 PR checks green.
- Fresh adversarial review completed.

## Stop conditions

- If the multi-year fit materially worsens the central distribution, treat that as evidence that the
  retention formulation or weather driver is inadequate; do not revert to 2023 to make the paper
  look better.
- Do not submit until the fresh review passes.
- Do not add new engineering thresholds or call them scientific evidence.
