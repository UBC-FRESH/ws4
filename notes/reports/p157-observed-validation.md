# P157 Dogrib comparison: corrected rows, per-cell growth, and hourly weather

Date: 2026-11-09
Branch: `feature/p157-observed-fire`
Tasks: P157.2 (#926), P157.5 (#939), P157.6 (#940), P157.7 (#941), P157.4 (#927)
Parent: P157 (#923)
Status: negative validation result; close-out in `notes/reports/p157-closeout.md`

## Correction

The first P157.2 result was computed with a north/south row flip. ESRI ASCII grids store row
zero at the north edge, but the comparison harness mapped projected y to rows from the south
edge. That flipped every observed mask and seeded the simulation in the wrong place.

The earlier P157.2 numbers (6,259 ha, −38.8% area bias, 14.29 km centroid error, IoU 0.070)
are invalid. P157.5 fixes the mapping and adds a top-row/bottom-row regression test.

## Question

Can the WS4 FBP/Huygens growth engine reproduce the observed Dogrib perimeter when it starts
from the observed 13:00 perimeter, uses the observed per-cell fuel and terrain, and runs with
the hourly weather to the 11:52 target?

## Inputs

- Fire: Dogrib (RWF085), Alberta, 2001.
- Start: observed 2001-10-16 13:00 perimeter, 935 ha across 2 polygons.
- Target: observed 2001-10-17 11:52 perimeter, 10,219 ha across 25 polygons, including spot
  fires.
- Grid: 357 × 223 cells at 100 m; custom NAD83 Transverse Mercator; row zero north.
- Fuel: observed FBP grid per cell. O1A/O1B maps to O1B; D1/D2 maps to D1; M1/M2 maps to M1
  with the labelled conifer percentage. These are documented assumptions.
- Terrain: slope and aspect derived from the north-first elevation grid; per-cell elevation.
- Weather: hourly wind, temperature, relative humidity, and precipitation. The FWI sequence
  starts from the sample dataset codes FFMC 89, DMC 58, and DC 482; event-day FFMC is 92.7
  and BUI is 98.7. FFMC is advanced with the standard equation on the hourly stream; BUI is
  held constant because the stream has no defensible hourly BUI conversion.
- Duration: 1,372 minutes, ending at the observed 11:52 perimeter.
- Ignition: every burnable cell inside the observed start perimeter (686 cells).
- Spotting: absent.
- Official scenario note: the sample dataset's Scenario 2 is 13:00–19:42 (402 min). The only
  observed final perimeter is 11:52 the next day. The 1,372-minute run is a time-matched test
  against that final, not the official 402-minute scenario; the 402-minute cases are retained
  for the official duration.

## Time alignment

This is the first time-matched run. It starts at 13:00 and ends at 11:52 the next day,
1,372 minutes later. The earlier 402-minute cases are retained as sensitivity runs but are
not time-matched to the final perimeter.

## Primary result: observed grid, hourly weather, 1,372 minutes

| Metric | Value |
| --- | --- |
| Simulated area | 29,509 ha |
| Observed area | 10,219 ha |
| Area bias | +188.8% |
| Simulated raster perimeter | 517.2 km |
| Observed raster perimeter | 160.2 km |
| Perimeter bias | +222.8% |
| Centroid distance | 3.01 km |
| IoU | 0.255 |
| Sorensen | 0.406 |
| Orientation error | 9.2° |
| Start cells | 686 |
| FFMC range | 92.7 → 84.7 |
| BUI | 98.7 constant |

The time-matched run moves the centroid close to the observed centroid and aligns the
principal axis. It grossly overpredicts area and perimeter: the simulated fire covers the
observed footprint and a large area to the north, west, and south. It does not reproduce the
observed final shape.

## Sensitivity set

| Scenario | Duration | Weather | Area (ha) | Area bias | Perimeter bias | Centroid (km) | IoU | Sorensen | Orientation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| observed grid, hourly | 1,372 | hourly | 29,509 | +188.8% | +222.8% | 3.01 | 0.255 | 0.406 | 9.2° |
| observed grid | 402 | constant | 8,203 | −19.7% | +11.6% | 9.85 | 0.206 | 0.342 | 29.2° |
| homogeneous C2 | 402 | constant | 13,852 | +35.6% | +75.2% | 6.17 | 0.264 | 0.418 | 0.7° |
| observed grid, hourly | 402 | hourly | 17,195 | +68.3% | +110.1% | 5.18 | 0.186 | 0.314 | 13.1° |
| observed grid, wind 27 | 402 | constant | 11,369 | +11.3% | +53.9% | 7.82 | 0.232 | 0.376 | 28.0° |
| observed grid, no wind | 402 | constant | 5,552 | −45.7% | −33.1% | 12.24 | 0.130 | 0.231 | 27.6° |
| observed grid | 1,372 | constant | 49,207 | +381.5% | +341.9% | 2.22 | 0.191 | 0.321 | 20.3° |

The 1,372-minute constant-weather run is worse than the hourly run. The hourly FFMC drop
reduces the overnight spread, but not enough to match the observed 10,219 ha. No case passes
all screens.

## Screening tolerances

These are screening tolerances, not operational acceptance.

| Check | Tolerance | Hourly 1,372 | Result |
| --- | --- | --- | --- |
| Area bias | ±50% | +188.8% | fail |
| Perimeter bias | ±35% | +222.8% | fail |
| Orientation error | ≤30° | 9.2° | pass |
| Centroid distance | ≤5 km | 3.01 km | pass |
| IoU | ≥0.30 | 0.255 | fail |
| Sorensen | ≥0.45 | 0.406 | fail |

The time-matched run passes the centroid and orientation checks but fails area, perimeter,
IoU, and Sorensen. That is a different failure from the 402-minute case: the location is
close, but the burned area is about three times too large.

## View

![Dogrib observed versus simulated perimeter](p157-dogrib-view.svg)

The SVG is generated by `scripts/benchmark_observed_fire.py` and served read-only at
`/api/fire/observed/dogrib.svg`. Orange is the hourly observed-grid simulation; dashed blue
is the observed 13:00 start; black is the observed final perimeter. The right panel carries
the run and target times, fuel, weather, and metric summary. The observed geometry is
read-only.

## Validation performed

- North-first row mapping with a top-row/bottom-row regression test.
- Homogeneous equivalence: a constant heterogeneous grid reproduces the existing homogeneous
  engine.
- Exact ellipse area and perimeter for a constant heterogeneous grid.
- Per-cell head ROS, length-to-breadth, and spread azimuth against the FBP kernel.
- Two-fuel and terrain-gradient tests.
- Time-dependent weather: constant steps reproduce the static run; a wind shift delays a far
  eastern arrival.
- Hourly weather steps cover the 23-row Dogrib event; overnight FFMC is lower than the start.

## What this does not verify

- **External model parity.** No runnable Prometheus/FARSITE oracle was used. This is an
  independent reimplementation of published FBP and Huygens logic, not a line-by-line parity
  test against a known-good executable.
- **Hourly BUI.** BUI is held at 98.7. The hourly FFMC is the standard FFMC equation applied
  to hourly weather, which is an approximation.
- **Spotting.** The observed final contains 25 polygons, including spot fires. The model has
  no spotting.
- **Fuel and weather uncertainty.** The observed fuel crosswalk and the constant BUI are
  documented assumptions, not calibrated values.
- **A regional calibration.** This is one historical case.

## Reproduction

```bash
python scripts/benchmark_observed_fire.py
```

Artifacts:

- `notes/reports/p157-dogrib-results.csv`
- `notes/reports/p157-dogrib-summary.json`
- `notes/reports/p157-dogrib-view.svg`

## Recommendation

Do not close P157 as a validated observed-fire match. The time-matched run is now real, but
it overpredicts area by 193% and fails perimeter and overlap. The next useful checks are an
external Prometheus/FARSITE parity run and a documented treatment of spotting and hourly BUI.
Do not calibrate the current cases to Dogrib.
