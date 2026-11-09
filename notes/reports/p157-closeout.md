# P157 close-out: observed-fire validation

Date: 2026-11-09
Parent issue: #923
Task: P157.4 (#927)
Branch: `feature/p157-observed-fire`
Status: completed with documented partial validation; PR queued for approval
Evidence report: `notes/reports/p157-observed-validation.md`

## Result

P157 is complete as a **documented partial validation**, not as an operational match. The
Dogrib inputs, comparison harness, and Scenario 2b run are reproducible, and the remaining
failures are explicit rather than calibrated away.

Primary case: documented Scenario 2b, 402 minutes from the observed 13:00 perimeter with
point ignition, the observed 13:00 perimeter as a non-fuel break plus 935 ha initial burned
area, hourly weather, the +15° landscape wind patch, and the 280° river-polygon patch.

| Metric | Result | Screen | Outcome |
| --- | --- | --- | --- |
| Simulated area | 16,241 ha | — | — |
| Initial burned area included | 935 ha | — | — |
| Observed area | 10,219 ha | — | — |
| Area bias | +58.9% | ±50% | fail |
| Simulated perimeter | 281.8 km | — | — |
| Observed perimeter | 160.2 km | — | — |
| Perimeter bias | +75.9% | ±35% | fail |
| Centroid distance | 1.77 km | ≤5 km | pass |
| IoU | 0.385 | ≥0.30 | pass |
| Sorensen | 0.556 | ≥0.45 | pass |
| Orientation error | 6.5° | ≤30° | pass |
| Ignition cells | 1 | — | — |
| Weather | hourly + patches | — | — |

The documented-scenario run passes location, orientation, and both overlap screens. It still
overpredicts area and perimeter. It is close enough in shape to be useful, but it is not an
operational match.

The time-matched Scenario 2b sensitivity (1,372 minutes to the observed 11:52 final) is
27,678 ha (+170.8%), perimeter +177.7%, centroid 1.07 km, IoU 0.304, Sorensen 0.466, and
8.0° orientation error. It passes centroid, orientation, and overlap; area and perimeter fail.

## Verified

- The Dogrib source, archive URL, licence caveat, CRS, local time zone, event times, and fuel
  crosswalk assumptions are recorded.
- The loader validates the perimeters, ignition, weather stream, FBP fuel grid, elevation grid,
  and the pinned Scenario 2b weather-patch polygon.
- The north-first ESRI row mapping has a top-row/bottom-row regression test.
- The comparison harness reports area, perimeter, centroid, IoU, Sorensen, and orientation.
- The observed-versus-simulated SVG is reproducible and served read-only at
  `/api/fire/observed/dogrib.svg`.
- The benchmark matrix reproduces the committed CSV, JSON, and SVG.
- Scenario 2b input tests cover point ignition, the start-perimeter fuel break, the +15°
  landscape wind offset, and the 280° polygon patch.
- The standard, model-to-model, and observed-fire evidence are separated in the design note,
  the evidence report, and the docs page.
- FireSTARR v0.9.29 deterministic was run on the same Dogrib reference fire at 200 m; the
  raw-wind comparison is in `notes/reports/p157-firestarr-comparison.md`. FireSTARR is closer
  on area; WS4 is closer on overlap and centroid. Prometheus and FARSITE were not run.
- Full suite: dashboard tests gate green; the coverage gate is at least 90%.
- Dashboard: `OVERALL: GREEN` on all seven gates.

## Accepted limits

These are explicit limitations of the phase, not hidden assumptions:

1. **External model parity is partial.** FireSTARR was run deterministically on the Dogrib
   raw-wind case; Prometheus and FARSITE were not run. There is no line-by-line parity test
   against a known-good executable.
2. **Burning-condition thresholds.** The sample scenario uses ISI, wind, and relative-humidity
   thresholds for growth. Those thresholds are not applied.
3. **WindNinja scenarios.** Scenario 2b uses the polygon patch, not the conservation-of-mass
   wind grids. Scenarios 2c/2d are not reproduced.
4. **Hourly BUI is held constant.** The hourly stream has no defensible BUI conversion. FFMC
   is advanced with the standard equation; BUI starts from the sample-dataset codes and stays
   at 98.7.
5. **No spotting.** The observed final has 25 polygons, including spot fires. The model has
   no spotting.
6. **One historical case.** A single Dogrib event is not a regional calibration.
7. **Scenario duration.** The documented Scenario 2 is 402 minutes (13:00–19:42). The only
   total observed perimeter is 11:52 the next day; the 1,372-minute run is a time-matched
   sensitivity, not the documented 402-minute scenario.

## Recommendation

Do not describe this model as operationally validated for observed fire perimeters. Keep the
area/perimeter failure and the accepted limits visible. The next useful work is the documented
burning-condition thresholds, WindNinja scenarios 2c/2d, and a BurnP3/Prometheus reference
comparison (#945). Prometheus installs under Wine but its GUI exits with a native
`SEHException`; BurnP3+FireSTARR is the most reproducible Linux path. Do not calibrate the
current cases to Dogrib.

## Reproduction

```bash
python scripts/benchmark_observed_fire.py
python -m pytest tests/test_benchmark_observed_fire_script.py tests/test_fire_comparison.py \
  tests/test_fire_observed.py tests/test_fire_observed_view.py -q
python scripts/dashboard.py
```

Artifacts:

- `notes/reports/p157-dogrib-results.csv`
- `notes/reports/p157-dogrib-summary.json`
- `notes/reports/p157-dogrib-view.svg`
- `docs/_static/fire-dogrib-view.svg`

## Pull request

PR #943 is queued for maintainer approval. Do not merge, tag, release, or change settings
without approval.
