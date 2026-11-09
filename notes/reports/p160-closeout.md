# P160 close-out: Dogrib burning conditions and wind-grid fidelity

Date: 2026-11-09
Parent issue: #947
Tasks: P160.1 (#948), P160.2 (#949), P160.3 (#950), P160.4 (#951)
Branch: `feature/p160-dogrib-wind-thresholds`
Status: implementation complete; PR queued for approval
Evidence: `notes/reports/p160-dogrib-matrix.md`

## Result

The threshold gate and both WindNinja scenarios were run on the fixed Dogrib matrix. Neither
change explains the remaining 2b area/perimeter overprediction.

| Scenario | Area (ha) | Area bias | Perimeter bias | Centroid (km) | IoU | Sorensen | Orientation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2b, no thresholds | 16,241 | +58.9% | +75.9% | 1.77 | 0.385 | 0.556 | 6.5° |
| 2b, thresholds | 16,241 | +58.9% | +75.9% | 1.77 | 0.385 | 0.556 | 6.5° |
| 2b, literal RH > 50 % | 937 | −90.8% | −80.1% | 13.93 | 0.082 | 0.152 | 57.7° |
| 2c, conservation of mass | 7,976 | −21.9% | +21.1% | 6.80 | 0.274 | 0.430 | 15.7° |
| 2d, conservation of mass and momentum | 5,251 | −48.6% | −14.9% | 8.99 | 0.237 | 0.384 | 32.3° |

Observed area: 10,219 ha. All simulated areas include the 935 ha initial burned area.

## What was added

- `BurningConditions`, an exclusive hourly gate on ISI, wind, and relative humidity. A failed
  step suspends new spread until a later step passes.
- Dogrib threshold values: ISI > 8, wind > 5 km/h, and the 50 % humidity condition.
- Both readings of the sample README's contradictory "greater than 50 %" wording. The physical
  maximum reading is used for the main matrix; the literal minimum reading is a sensitivity.
- `ws4.fire.wind`: paired WindNinja angle/velocity loading, geometry and value checks,
  provenance, and nearest-direction selection.
- The fixed 2b/2c/2d benchmark matrix with threshold and wind-grid provenance in the CSV/JSON.
- The `fire-wind` reference page and `p160-dogrib-2b-view.svg`.

## Verification

- Threshold unit tests cover strict boundaries, temporary failure, missing weather steps, and
  both humidity readings.
- Wind-grid tests cover paired loading, mismatched geometry, missing companions, circular
  direction selection, north-first cells, and growth use.
- Benchmark tests cover the base scenarios, extra threshold scenarios, and optional wind-grid
  scenarios.
- Dashboard: `OVERALL: GREEN` on all seven gates.
- The 2b/2c/2d CSV, JSON, and report reproduce from the documented command.

## Accepted limits

- This is one historical fire and one event window; it is not a calibration.
- The WindNinja grids are third-party validation data with no explicit licence file in the
  archive. They are not committed; the matrix was run from a local extraction of the public
  archive.
- Wind-grid selection uses the nearest available direction, not temporal interpolation or the
  original Prometheus activation logic.
- The hourly stream still holds BUI at 98.7 and does not model spotting.
- The 2c/2d runs use no polygon patches; the comparison is wind-method only.
- No observed-fire parameter was fitted.

## Recommendation

Keep the 2b polygon-patch result as the documented validation case. The threshold and
WindNinja routes have been tested and do not improve the screens. The next evidence-bearing
step is a second independent observed fire and a calibration/holdout protocol; P159 remains a
separate, planned surrogate study.

Do not merge, tag, release, or change settings without maintainer approval.

## Pull request

Stacked on PR #943 (`feature/p157-observed-fire`). Retarget to `main` after #943 merges.
PR: #952.
