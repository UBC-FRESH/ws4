# TSA 46 post-fire recovery pilot

Real-data pilot for the NTEMS post-disturbance recovery product. The layer
classifies pixels burned by wildfire in 1986-2012 as:

- `1` — faster than the ecozonal baseline
- `2` — slower than the baseline
- `3` — not recovered by the end of the 2017 observation period

## Source

- Product: Canada Forest Post-Disturbance Recovery Rate, fire layer.
- Natural Resources Canada / NTEMS; 30 m, EPSG:3978.
- Disturbance: wildfire 1986-2012; observation 1985-2017.
- Licence: Open Government Licence - Canada.
- Citation: White et al. 2022, *Mapping, validating, and interpreting
  spatio-temporal trends in post-disturbance forest recovery*, Remote Sensing of
  Environment 271, 112904.

The example stores a 5 km subset around `1021022, 798654` EPSG:3005 in TSA 46,
plus 33 VRI polygons intersecting that window. Two blocks have no recovery
pixels and are `outside_footprint`, not failed.

## Files

| File | Purpose |
| --- | --- |
| `recovery_tsa46_5km.tif` | 30 m fire-recovery-rate subset. |
| `blocks.geojson` | 33 TSA46 VRI polygons with `FEATURE_ID` and `area_ha`. |
| `regen_status.csv` | Per-block fractions and dominant recovery status. |
| `regen_status_summary.csv` | Blocks/area by dominant status. |
| `recovery_metadata.json` | Source, windows, CRS, class map, citation. |

## Command

```bash
ws4 recovery ingest \
  --raster examples/recovery_tsa46/recovery_tsa46_5km.tif \
  --blocks examples/recovery_tsa46/blocks.geojson \
  --block-id-field FEATURE_ID \
  --output examples/recovery_tsa46/regen_status.csv \
  --metadata examples/recovery_tsa46/recovery_metadata.json \
  --summary examples/recovery_tsa46/regen_status_summary.csv \
  --source-version "NTEMS post-disturbance recovery rate / White et al. 2022"
```

## Results

- 33 blocks, 19,806 ha.
- 31 blocks with recovery pixels; 2 outside the footprint.
- **31/31 recovered-footprint blocks are dominated by `not_recovered`**.
- Burned recovery area: **5,224 ha**.
- No block in this window is dominated by faster recovery; 13 pixels in the
  subset are class 2 (slower), but they do not dominate any block.

## Caveats

- Spectral recovery is not tree survival or stocking. It is a Landsat
  spectral-recovery metric.
- The observation window ends in 2017; a block can still be recovering.
- A block outside the fire footprint is not a regeneration failure.
- This is a 5 km TSA46 pilot, not a provincial failure map.
- The layer does not enter the objective; it is a fragment attribute for
  inspection and later constraints.
