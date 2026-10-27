# TSA 23 post-fire recovery pilot

Full-estate application of the NTEMS post-disturbance recovery layer to TSA 23.
This is the fire-oriented instance; it replaces the earlier 5 km TSA 46 smoke
subset for planning interpretation.

## Source

- Canada Forest Post-Disturbance Recovery Rate, fire layer.
- NTEMS / Natural Resources Canada, 30 m, EPSG:3978.
- Wildfire disturbance 1986-2012; observation 1985-2017.
- Classes: 1 faster than baseline, 2 slower, 3 not recovered by 2017.
- Licence: Open Government Licence - Canada.
- Citation: White et al. 2022, Remote Sensing of Environment 271, 112904.

## Files

| File | Purpose |
| --- | --- |
| `recovery_tsa23_30m.tif` | 30 m recovery-rate subset over TSA 23. |
| `regen_status.csv` | Per-block status fractions for all 102,128 TSA 23 blocks. |
| `regen_status_summary.csv` | Blocks/area by dominant status. |
| `baseline_schedule_recovery.csv` | Existing baseline schedule joined to recovery status. |
| `recovery_metadata.json` | Source, windows, CRS, class map, citation. |

The full block geometry is the external TSA 23 instance file
`runtime/gis/tsa23_blocks.geojson` (266 MB); it is not duplicated here.

## Command

```bash
ws4 recovery ingest \
  --raster examples/recovery_tsa23/recovery_tsa23_30m.tif \
  --blocks /path/to/femic-tsa23-instance/runtime/gis/tsa23_blocks.geojson \
  --method raster \
  --block-id-field block_id \
  --output examples/recovery_tsa23/regen_status.csv \
  --metadata examples/recovery_tsa23/recovery_metadata.json \
  --summary examples/recovery_tsa23/regen_status_summary.csv \
  --source-version "NTEMS post-disturbance recovery rate / White et al. 2022"
```

`--method raster` rasterizes block ids once and counts classes with `bincount`;
it is the full-estate path. The smaller TSA 46 example uses polygon masks.

## Results

- TSA 23: 102,128 blocks, 988,816 ha.
- 1,555 blocks in the fire-recovery footprint.
  - **1,497 not recovered**, 21,948 ha, 5,727 ha burned.
  - **58 slower**, 745 ha, 176 ha burned.
  - No block dominated by faster recovery.
- 100,573 blocks are `outside_footprint`, not failures.
- Existing baseline schedule: 2,000 blocks, all at offset 0.
  - **29 scheduled blocks are not recovered** (212 ha).
  - 2 scheduled blocks are slower (8 ha).
  - 1,969 scheduled blocks are outside the footprint.

## Interpretation

The recovery layer is a Landsat spectral-recovery metric, not tree survival or
stocking. The observation window ends in 2017. The 29 not-recovered blocks in
the existing schedule are the first candidates for a **scenario** that defers
harvest; this is not an objective or constraint change until the volume impact
is reviewed.

## Caveats

- 30 m spectral recovery is not a field regeneration survey.
- A block outside the fire footprint is not a failure.
- The baseline schedule has only 2,000 rows at offset 0; it is a smoke schedule,
  not the full TSA 23 AAC plan.
- The layer is read-only in this slice.
