# P164.8 real-layer full-estate integration

Status: integration evidence

This run replaces the full-estate homogeneous default inside the 24 calibrated tiles with the
real VRI/SRTM/water layers already cached for those tiles.

## Setup

- full TSA24 support map: 1,957 × 2,237 cells at 250 m
- 349,650 real-layer cells inside the 24 calibrated tiles
- 799,917 support cells outside the calibrated tiles use a homogeneous C2 default
- 1,080,986 burnable support cells
- regional suppression configs from `work/fire_regime/results/region-calibration.json`
- three ignitions, one in each of `t01`, `t13`, and `t22`
- 10 active hours per day, two active days
- full compiled TSA24 dataset

## Result

- source emitted 15 fire events
- burned area: 55.47 ha
- full dataset load: 127.8 s
- full-estate process evaluation completed

## Boundary

Only 31% of support cells have real VRI/SRTM layers. The remainder uses a homogeneous C2 default.
This is a full-estate integration proof with partial real-layer coverage, not a full TSA24
real-layer forecast.

The next data task is to extend the VRI/SRTM tile cache to the remaining support cells. No new
fire-size calibration is implied by this step.
