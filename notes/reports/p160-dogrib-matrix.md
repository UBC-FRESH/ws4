# P160 Dogrib burning-condition and wind-grid matrix

Date: 2026-11-09
Phase: P160 (Dogrib burning conditions and wind-grid fidelity)
Tasks: P160.1 (#948), P160.2 (#949), P160.3 (#950)
Branch: `feature/p160-dogrib-wind-thresholds`
Evidence: `notes/reports/p160-dogrib-matrix.csv`, `notes/reports/p160-dogrib-matrix.json`

## Question

Do the documented Prometheus burning-condition thresholds or the WindNinja Scenario 2c/2d
wind grids explain the remaining Dogrib area and perimeter overprediction?

## Fixed inputs

All rows use the same observed fire, 100 m grid, per-cell FBP fuel, slope/aspect/elevation,
hourly weather stream, point ignition, observed 13:00 perimeter as a non-fuel break with the
935 ha start area included, and the 402-minute documented Scenario 2 duration. The only
changed input is the wind treatment, except for the explicit threshold sensitivity.

- Thresholds: hourly ISI > 8, wind > 5 km/h, relative humidity 50 % condition.
- Scenario 2b: +15° landscape wind patch until 18:30 and 280° river patch until 20:00.
- Scenario 2c: conservation-of-mass WindNinja grids.
- Scenario 2d: conservation-of-mass-and-momentum WindNinja grids.
- Wind grids are selected by nearest available direction; no interpolation.

## Result

| Scenario | Simulated area (ha) | Area bias | Perimeter bias | Centroid (km) | IoU | Sorensen | Orientation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2b, no thresholds | 16,241 | +58.9% | +75.9% | 1.77 | 0.385 | 0.556 | 6.5° |
| 2b, thresholds | 16,241 | +58.9% | +75.9% | 1.77 | 0.385 | 0.556 | 6.5° |
| 2b, literal RH > 50 % | 937 | −90.8% | −80.1% | 13.93 | 0.082 | 0.152 | 57.7° |
| 2c, conservation of mass | 7,976 | −21.9% | +21.1% | 6.80 | 0.274 | 0.430 | 15.7° |
| 2d, conservation of mass and momentum | 5,251 | −48.6% | −14.9% | 8.99 | 0.237 | 0.384 | 32.3° |

Observed area: 10,219 ha. The 2b and 2c/2d simulated areas include the 935 ha initial burned
area.

## Interpretation

- The threshold gate does **not** change Scenario 2b. The event weather already passes the
  ISI, wind, and plausible RH-maximum conditions. The thresholds are not the explanation for
  the area/perimeter overprediction.
- The literal README wording, RH greater than 50 %, stops all growth and leaves only the
  initial burned area plus one ignition cell. This is recorded as a sensitivity, not adopted
  as the scenario interpretation. The event weather is 18–40 % RH, and a greater-than rule
  would prevent the observed run.
- Scenario 2c underburns by 21.9 %. Its area is closer than 2b, but its centroid, IoU,
  Sorensen, and orientation all fail the P157 screens.
- Scenario 2d underburns more and performs worst, consistent with the Prometheus sample
  report. It fails every spatial screen.
- The WindNinja grids therefore do not explain the remaining 2b overprediction. The best
  current result remains the 2b polygon-patch run.

## Accepted limits

- This is one historical fire and one event window; it is not a calibration.
- The wind grids are third-party validation data with no explicit licence file in the
  archive. They are not committed to the repository; the matrix was run from a local
  extraction of the public archive.
- The hourly stream still holds BUI at 98.7 and does not model spotting.
- The wind-grid selection uses the nearest available direction, not temporal interpolation or
  the original Prometheus grid activation logic.
- The 2c/2d rows use no polygon patches; the comparison is wind-method only.
- No observed-fire parameter was fitted.

## Reproduction

The full grids are in the public Dogrib sample archive, under `conserv_mass/` and
`conserv_mass_moment/`. After extracting those directories to a local root:

```bash
python scripts/benchmark_observed_fire.py \
  --wind-grids-root <extracted-Dogrib-root> \
  --output notes/reports/p160-dogrib-matrix.csv \
  --summary notes/reports/p160-dogrib-matrix.json \
  --view notes/reports/p160-dogrib-2b-view.svg
```

The committed CSV and JSON are the evidence for this report. `p160-dogrib-2b-view.svg` is the
2b comparison view; the table above is the 2b/2c/2d matrix.

## Recommendation

Keep the 2b polygon-patch result as the documented validation case. Do not calibrate to
Dogrib. The next evidence-bearing step is a second independent fire and a calibration/holdout
protocol; the WindNinja route has been tested and does not improve the current screens.
