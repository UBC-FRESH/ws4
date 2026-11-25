# P164.9 FireSTARR TSA24 tile smoke test

Date: 2026-11-25
Status: software compatibility check, not an observed-fire benchmark

## Outcome

The earlier FireSTARR v0.9.29 attempt failed with SIGFPE after loading TSA24 rasters. The failure was
not accepted as final. A one-tile run now completes deterministically after:

- converting the fuel and DEM rasters to tiled GeoTIFFs;
- replacing non-fuel code 0 with the FireSTARR non-fuel code 101;
- writing the DEM as an integer raster;
- starting the weather CSV at 00:00 rather than 13:00;
- providing a one-cell start raster and a complete daily weather record.

The synthetic 30 km tile used a one-cell ignition (6.25 ha) and a one-day deterministic run. FireSTARR
ended day 1 at 75 ha. A same-tile, same-weather WS4 one-cell run produced 2,743.8 ha for the first
day. The inputs are not matched closely enough to call this a parity test, but the divergence is
large and is recorded rather than hidden.

## Reproducible shape

Inputs:

- `grid/default/fuel.tif`: uint8 FBP codes, tiled;
- `grid/default/dem.tif`: int16 elevation, tiled;
- `start.tif`: uint8 one-cell start perimeter;
- `weather.csv`: the FireSTARR column order, hourly, starting at 00:00.

Command shape:

```bash
firestarr OUT YYYY-MM-DD LAT LON 13:00 \
  --raster-root GRID \
  --wx weather.csv \
  --perim start.tif \
  --deterministic \
  --ffmc 92 --dmc 40 --dc 300 --apcp_prev 0 \
  --tz -8 --output_date_offsets '[1]' \
  --log firestarr.log
```

## Observed event attempt

A one-cell point-ignition run was also attempted on the observed post-2018 event G13085 (112.3 ha,
34 days) using the same tile/weather workflow. FireSTARR reached 20,525 ha, versus 237.5 ha for the
WS4 all-year event reconstruction and 1,443.8 ha for the post-2018 map. This is not a like-for-like
benchmark: FireSTARR has no suppression resources, the ignition is a point rather than the observed
start perimeter, and the startup moisture state is approximate. It does show that the external
comparison is unresolved rather than successful.

The next external-benchmark step is a matched observed TSA24 event with suppression and a documented
start perimeter, not another synthetic tile.
