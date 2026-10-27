# DIS-04 TSA 23 full-estate recovery pilot

Date: 2026-10-27
Candidate: DIS-04
Scope: apply the public NTEMS fire recovery layer to TSA 23, the fire-oriented
instance, and check it against the existing baseline schedule.

## Source

- Canada Forest Post-Disturbance Recovery Rate, fire layer.
- NTEMS / Natural Resources Canada, 30 m, EPSG:3978.
- Wildfire disturbance 1986-2012; observation 1985-2017.
- Classes: 1 faster, 2 slower, 3 not recovered by 2017.
- OGL-C; White et al. 2022, Remote Sensing of Environment 271, 112904.

## Implementation

- `ws4 recovery ingest --method raster` rasterizes block ids once and counts
  recovery classes with `bincount`; the polygon-mask path remains for small
  pilots.
- Per-block output: fractions, burned area, dominant status, and dominant
  fraction. `outside_footprint` is not a failure.
- Tests cover polygon fractions, outside-footprint handling, source version,
  summary, and the rasterized full-estate path.

## Full-estate result

TSA 23 has 102,128 blocks and 988,816 ha.

- 1,555 blocks in the fire footprint.
- **1,497 not recovered**: 21,948 ha, 5,727 ha burned.
- **58 slower**: 745 ha, 176 ha burned.
- No block dominated by faster recovery.
- 100,573 blocks outside the footprint, reported but not treated as failure.

Existing `runtime/ws4/schedule_baseline.csv` has 2,000 blocks, all at offset 0:

- 29 scheduled blocks are not recovered (212 ha).
- 2 scheduled blocks are slower (8 ha).
- 1,969 scheduled blocks are outside the footprint.

## Next use

The 29 not-recovered blocks in the baseline schedule are the first candidate for
a **defer-harvest scenario**. That scenario should be compared against baseline
for volume and area before any constraint is introduced. This slice does not
change the objective or constraints.

## Caveats

- Recovery is Landsat spectral recovery, not tree survival or stocking.
- The observation window ends in 2017.
- A block outside the footprint is not a failure.
- The 2,000-row baseline is a smoke schedule, not the full AAC plan.
- Geometry is not duplicated in the example; the TSA 23 block GeoJSON is 266 MB.
