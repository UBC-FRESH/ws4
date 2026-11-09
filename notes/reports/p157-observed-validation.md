# P157 Dogrib comparison: Scenario 2b, per-cell fuel, and hourly weather

Date: 2026-11-09
Branch: `feature/p157-observed-fire`
Tasks: P157.2 (#926), P157.5 (#939), P157.6 (#940), P157.7 (#941), P157.8 (#942), P157.4 (#927)
Parent: P157 (#923)
Status: partial validation; close-out in `notes/reports/p157-closeout.md`

## Correction

The first P157.2 result was computed with a north/south row flip. ESRI ASCII grids store row
zero at the north edge, but the comparison harness mapped projected y to rows from the south
edge. That flipped every observed mask and seeded the simulation in the wrong place.

The earlier P157.2 numbers (6,259 ha, −38.8% area bias, 14.29 km centroid error, IoU 0.070)
are invalid. P157.5 fixes the mapping and adds a top-row/bottom-row regression test.

## Question

Can the WS4 FBP/Huygens growth engine reproduce the observed Dogrib fire when it uses the
documented Scenario 2 inputs: observed per-cell fuel and terrain, hourly weather, point
ignition, the 13:00 perimeter as a fuel break, the +15° landscape wind patch, and the 280°
river-polygon wind patch?

## Inputs

- Fire: Dogrib (RWF085), Alberta, 2001.
- Start: observed 2001-10-16 13:00 perimeter, 935 ha across 2 polygons.
- Target: observed 2001-10-17 11:52 final perimeter, 10,219 ha across 25 polygons, including
  spot fires.
- Grid: 357 × 223 cells at 100 m; custom NAD83 Transverse Mercator; row zero north.
- Fuel: observed FBP grid per cell. O1A/O1B maps to O1B; D1/D2 maps to D1; M1/M2 maps to M1
  with the labelled conifer percentage.
- Terrain: slope and aspect derived from the north-first elevation grid; per-cell elevation.
- Weather: hourly wind, temperature, relative humidity, and precipitation. The FWI sequence
  starts from the sample codes FFMC 89, DMC 58, and DC 482; event-day FFMC is 92.7 and BUI is
  98.7. FFMC is advanced with the standard equation on the hourly stream; BUI is held
  constant because the stream has no defensible hourly BUI conversion.
- Scenario 2b patches: +15° added to wind directions from 13:00 to 18:30; 280° inside the
  river-polygon patch from 13:00 to 20:00.
- Ignition: the observed point, not the whole start perimeter.
- Fuel break: the observed 13:00 perimeter is converted to non-fuel and included in the
  burned mask as initial area (935 ha).
- Duration: 402 minutes (13:00–19:42), the documented Scenario 2 duration. A 1,372-minute
  sensitivity runs to the observed 11:52 final time.
- Spotting: absent.

## Time alignment

The documented Scenario 2 is 13:00–19:42 (402 min). The only total observed perimeter is
11:52 the next day. The 402-minute run is therefore compared with a final perimeter that
includes later growth. The 1,372-minute run is time-matched to the final, but it is not the
documented 402-minute scenario.

## Primary result: Scenario 2b, 402 minutes

| Metric | Value |
| --- | --- |
| Simulated area | 16,241 ha |
| Initial burned area included | 935 ha |
| Observed area | 10,219 ha |
| Area bias | +58.9% |
| Simulated raster perimeter | 281.8 km |
| Observed raster perimeter | 160.2 km |
| Perimeter bias | +75.9% |
| Centroid distance | 1.77 km |
| IoU | 0.385 |
| Sorensen | 0.556 |
| Orientation error | 6.5° |
| Ignition cells | 1 |
| Weather | hourly + patches |

This is a substantial spatial improvement over the raw-wind case. The centroid is 1.77 km
away, IoU is 0.385, Sorensen is 0.556, and the principal axis is within 6.5°. The simulated
area and perimeter still overpredict by 59% and 76%.

## Sensitivity set

| Scenario | Duration | Area (ha) | Area bias | Perimeter bias | Centroid (km) | IoU | Sorensen | Orientation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Scenario 2b | 402 | 16,241 | +58.9% | +75.9% | 1.77 | 0.385 | 0.556 | 6.5° |
| observed grid, hourly, raw wind | 402 | 17,195 | +68.3% | +110.1% | 5.18 | 0.186 | 0.314 | 13.1° |
| observed grid, constant wind | 402 | 8,203 | −19.7% | +11.6% | 9.85 | 0.206 | 0.342 | 29.2° |
| homogeneous C2 | 402 | 13,852 | +35.6% | +75.2% | 6.17 | 0.264 | 0.418 | 0.7° |
| Scenario 2b | 1,372 | 27,678 | +170.8% | +177.7% | 1.07 | 0.304 | 0.466 | 8.0° |
| observed grid, hourly, raw wind | 1,372 | 29,509 | +188.8% | +222.8% | 3.01 | 0.255 | 0.406 | 9.2° |
| observed grid, constant wind | 1,372 | 49,207 | +381.5% | +341.9% | 2.22 | 0.191 | 0.321 | 20.3° |

The Scenario 2b patches improve centroid and overlap at both durations. The area and
perimeter remain too large.

## Screening tolerances

These are screening tolerances, not operational acceptance.

| Check | Tolerance | Scenario 2b, 402 | Result |
| --- | --- | --- | --- |
| Area bias | ±50% | +58.9% | fail |
| Perimeter bias | ±35% | +75.9% | fail |
| Orientation error | ≤30° | 6.5° | pass |
| Centroid distance | ≤5 km | 1.77 km | pass |
| IoU | ≥0.30 | 0.385 | pass |
| Sorensen | ≥0.45 | 0.556 | pass |

The documented-scenario run passes location, orientation, and overlap. It fails area and
perimeter. This is the first P157 case that is close enough in shape to be useful; it is not
an operational match.

## View

![Dogrib observed versus simulated perimeter](p157-dogrib-view.svg)

The SVG is generated by `scripts/benchmark_observed_fire.py` and served read-only at
`/api/fire/observed/dogrib.svg`. Orange is the Scenario 2b simulation including the initial
burned area; dashed blue is the observed 13:00 start; black is the observed final perimeter.
The right panel carries the run and target times, fuel, weather, and metric summary. The
observed geometry is read-only.

## Validation performed

- North-first row mapping with a top-row/bottom-row regression test.
- Homogeneous equivalence: a constant heterogeneous grid reproduces the existing homogeneous
  engine.
- Exact ellipse area and perimeter for a constant heterogeneous grid.
- Per-cell head ROS, length-to-breadth, and spread azimuth against the FBP kernel.
- Two-fuel, terrain-gradient, nodata, and wind-patch tests.
- Time-dependent weather: constant steps reproduce the static run; a wind shift delays a far
  eastern arrival.
- Scenario 2b input tests: point ignition, start-perimeter fuel break, +15° landscape offset,
  and 280° polygon patch.
- Hourly weather steps cover the 23-row Dogrib event; overnight FFMC is lower than the start.

## External-model comparison

FireSTARR v0.9.29 deterministic was run on a 200 m comparison grid covering the full Dogrib
extent, with the same observed start perimeter, fuel, terrain, and weather. It does not include
the Scenario 2b polygon wind patch. The raw-wind comparison is:

| Model | Area (ha) | Area bias | IoU | Sorensen | Centroid (km) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Observed | 10,132 | — | — | — | — |
| WS4 raw wind | 29,480 | +191.0% | 0.252 | 0.403 | 3.09 |
| FireSTARR deterministic | 13,808 | +36.3% | 0.140 | 0.246 | 6.91 |

FireSTARR is closer on area; WS4 is closer on overlap and centroid. Full details and caveats:
`notes/reports/p157-firestarr-comparison.md`.

## What this does not verify

- **External model parity is partial.** FireSTARR was run deterministically on the raw-wind
  case. Prometheus and FARSITE were not run; there is no line-by-line parity test against a
  known-good executable.
- **Burning conditions.** The sample scenario requires thresholds on ISI, wind, and relative
  humidity for growth. Those thresholds are not applied.
- **WindNinja grids.** Scenario 2b uses the polygon patch, not the conservation-of-mass wind
  grids. Scenarios 2c/2d are not reproduced.
- **Hourly BUI.** BUI is held at 98.7. The hourly FFMC is the standard FFMC equation applied
  to hourly weather, which is an approximation.
- **Spotting.** The observed final contains 25 polygons, including spot fires. The model has
  no spotting.
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

Do not close P157 as an operational match. Scenario 2b now passes centroid, orientation, and
overlap; area is 59% high and perimeter 76% high. The next useful checks are the documented
burning-condition thresholds and the WindNinja scenarios, followed by external parity. Do not
calibrate to Dogrib.
