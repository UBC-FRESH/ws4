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
ended day 1 at 75 ha. This is a software compatibility result: it does not compare against an observed
TSA24 fire and is not an external validation.

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

The next external-benchmark step is an observed TSA24 event with a documented start perimeter and
weather, not another synthetic tile.
