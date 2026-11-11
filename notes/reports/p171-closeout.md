# P171 close-out: terrain sensitivity

Date: 2026-11-11
Phase: P171 (#1016)
Branch: `feature/p171-terrain-sensitivity`
Pull request: #1020

## Outcome

Added a flat-terrain diagnostic switch and reran the six cases with DEM and flat terrain.

## Result

- median DEM area ratio: 10.35x;
- median flat area ratio: 10.35x;
- flat terrain reduced the ratio in **0 of 6** cases;
- IoU was unchanged.

Terrain is not the cause of the overprediction in this path.

## Decision

P171 is a negative terrain result. The remaining candidates are fuel mapping, ROS scale, or
containment/stopping. No calibration was applied. P164.3 remains paused.

## Limits

- Six cases, one fuel/terrain tile.
- The flat switch sets slope to zero and aspect to 180; it does not change fuel.
- Reanalysis weather and daily perimeters.

## Verification

- Dashboard: GREEN.
- Flat-terrain test green.
- No merge without maintainer approval.
