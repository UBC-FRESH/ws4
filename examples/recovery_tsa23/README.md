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
| `deferred_blocks.csv` | 411 scheduled not-recovered blocks. |
| `recovery_scenario_comparison.csv` | Baseline vs deferral scenario volumes/area. |
| `recovery_scenario_summary.json` | Scenario summary. |
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
- Existing `ft_warm` schedule: 44,388 blocks, offsets 0-4.
  - **411 scheduled blocks are not recovered** (6,048 ha).
  - 22 scheduled blocks are slower (255 ha).
  - 43,955 scheduled blocks are outside the footprint.

## Interpretation

The recovery layer is a Landsat spectral-recovery metric, not tree survival or
stocking. The observation window ends in 2017.

### Deferral scenario

Deferring treatments on the 411 not-recovered scheduled blocks:

- harvested volume: **138.50M -> 137.12M m3** (-1.378M m3, **-1.00%**)
- treated area: **317,710 -> 314,131** (-3,579; **-1.13%**)
- deferring both not-recovered and slower blocks: -1.424M m3 (**-1.03%**),
  -3,790 treated area.

The block area of 6,048 ha is larger than the treated-area change because some
scheduled treatments are not operable at the block's current track/age. The
reduction is a scenario result, not an objective or constraint change.

## Caveats

- 30 m spectral recovery is not a field regeneration survey.
- A block outside the fire footprint is not a failure.
- The baseline schedule has only 2,000 rows at offset 0; it is a smoke schedule,
  not the full TSA 23 AAC plan.
- The layer is read-only in this slice.
