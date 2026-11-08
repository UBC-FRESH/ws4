# P156 close-out: credible fire behaviour and growth

Phase: P156
Branch: `feature/p156-fire-behaviour`
Status: ready for maintainer review; no merge performed
Date: 2026-11-08
Parent issue: #890

## What the phase delivered

- P156.1 fire environment and fuel contracts.
- P156.2 Rothermel surface-fire kernel.
- P156.3 crown fire initiation and propagation.
- P156.4 Huygens growth, slope-adjusted effective wind, barriers, perimeter snapshots, and the P144 fragment bridge.
- P156.5 FBP kernel coupling to the event log and accounts.
- P156.6 benchmark, ensemble, and this report.
- P156.7 Canadian FWI moisture codes.
- P156.8 Canadian FBP fuel types and surface fire.
- P156.9 VRI-to-FBP fuel-type mapping with provenance.

The phase branch is `feature/p156-fire-behaviour`. The benchmark commit is `44961bb`. Earlier
phase commits include `7367ef6`, `977b320`, `421e1ea`, and `603909f`.

## Standard-case evidence

These are the existing kernel and growth tests, rerun in the full dashboard.

| Layer | Reference | Result |
| --- | --- | --- |
| Rothermel surface | R `Rothermel` 13 Anderson models, custom dynamic example, 15-point A3 wind/slope grid | within 0.01 in the reported units |
| FWI codes | `cffdrs` ten-day sequences at latitude 55 and latitude 20 | within `1e-4` for all seven codes |
| FBP surface | `cffdrs` 17 fuel types at FFMC 90, BUI 60, 10 km/h, flat, and a 320-point grid | within 0.02 |
| FBP crown | `cffdrs` base table, 320-point grid, three C6 cases | CFB/ROS within 0.02, HFI within 1.0 kW/m, fire description exact |
| Slope adjustment | `cffdrs` 40 wind/slope/fuel cases | within 0.02 km/h and 0.1 degree |
| Growth geometry | analytic ellipse and barrier cases | length/width within 10 percent; barrier stops the front |
| VRI mapping | representative fixture | expected type and rule for every record |

The Rothermel, FBP, crown, FWI, and slope references were generated with the public R
packages as validation oracles only. They are not runtime dependencies.

## Benchmark evidence

The benchmark uses the public FBP elliptical growth model. It is a geometry benchmark: the
same FBP head ROS feeds the analytic ellipse and the Huygens engine. The head ROS itself is
validated by the standard cases above.

Method:

- five fuels: C2, C3, C7, M1, S1;
- four wind speeds: 0, 10, 20, and 30 km/h;
- FFMC 90, BUI 60, flat ground;
- 60-minute duration, 10 m grid, 16 primitive directions, flat-ground head ROS;
- 20 scenarios.

| Metric | Mean absolute relative error | Maximum absolute relative error |
| --- | --- | --- |
| Length | 1.3 percent | 8.4 percent |
| Width | 1.9 percent | 8.4 percent |
| Area | 7.4 percent | 16.4 percent |
| Perimeter | 25.2 percent | 30.9 percent |

Tolerances used for this raster benchmark: area at most 20 percent, length and width at most
10 percent, and perimeter at most 35 percent. All pass. The area error grows with wind
because the discrete direction set still has some anisotropy. The perimeter is the raster
cell-edge length and is systematically above the smooth ellipse; that is a raster effect,
not a head-ROS error.

Per-scenario data: `notes/reports/p156-benchmark.csv`.
Summary: `notes/reports/p156-benchmark-summary.json`.

## Weather and fuel-moisture ensemble

The ensemble is a deterministic scenario grid, not a Monte Carlo sample from a calibrated
weather distribution.

- fuels C2, C3, C7;
- FFMC 85, 90, 95;
- BUI 30, 60, 90;
- wind 10 and 20 km/h;
- 60 minutes;
- 54 scenarios.

| Statistic | Area (ha) |
| --- | --- |
| Minimum | 0.02 |
| P10 | 0.14 |
| P50 | 10.13 |
| P90 | 199.85 |
| Mean | 51.72 |
| Maximum | 383.74 |

Exceedance probabilities: area at least 1 ha is 0.778, at least 10 ha is 0.500, at least
50 ha is 0.241, and at least 100 ha is 0.167. These are empirical frequencies over the
scenario grid, not calibrated risk probabilities.

## Visual evidence

Visual validation is **not** claimed in this phase. The scene package and viewer are on the
P155 branch. P156.5 records the event attributes the viewer must consume: fuel, weather,
slope, effective wind, ROS, head-fire intensity, flame length, crown fraction, fuel
consumption, smoke strength, and kernel version. The parent acceptance criterion about
viewer flames is deferred to P155 and is not evidence for P156.

## Phase acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Standard fuel models and published cases reproduce within a stated tolerance | Standard-case table above | pass |
| ROS responds monotonically to wind, slope, and moisture and goes to zero at the moisture of extinction | Rothermel tests | pass |
| A fire event records fuel, weather, slope, and kernel version | P156.5 event attributes and tests | pass |
| Growth produces an elliptical perimeter and a wind/slope-driven shape | P156.4 tests and FBP ellipse benchmark | pass |
| Viewer flame length and smoke derive from fireline intensity and fuel consumption | P155 scene branch | deferred, tracked in P155 |
| Dashboard green | full dashboard run | pass |

## Verification

- `python scripts/dashboard.py` with `PYTHONPATH=.`: **OVERALL: GREEN** on lint, format,
  types, tests, validator, docs, and docstrings.
- Fire and ecosystem fire suite: 115 tests.
- Benchmark rerun command: `python scripts/benchmark_fire_growth.py`.
- Benchmark artifacts written to `notes/reports/`.

The `PYTHONPATH=.` note is local: the editable install in the development environment points
at a different checkout, so the worktree package must be forced for the docstring gate. CI
installs the branch package, so it does not need that override.

## Limits and what was not verified

- No observed fire perimeter is used. The public FBP ellipse is a growth model, but it shares
  the FBP head ROS with the engine; this is not an independent landscape validation.
- The growth grid is homogeneous in fuel and weather. No DEM, fuel raster, or fragment-scale
  heterogeneity is exercised.
- The perimeter is a raster cell-edge length, not a sub-cell contour.
- The ensemble is a deterministic scenario grid, not a regional or seasonal probability model.
- C6 slope adjustment is unsupported. Spotting and ember transport are not implemented.
- The VRI mapping is a transparent rule set, not a regional calibration.
- The viewer coupling and visual evidence remain P155.

## Recommendation

Approve the P156 close-out. After approval: merge the phase pull request, delete the phase
branch, close parent #890, and continue P155 for the scene and viewer work. No merge, tag,
release, or settings change has been performed.
