# P169 close-out: growth trajectory diagnosis

Date: 2026-11-11
Phase: P169 (#1006)
Branch: `feature/p169-growth-trajectory`
Pull request: #1010

## Outcome

Added configurable daily snapshots and neighbor radius to `run_observed_case`, then compared
simulated daily area to observed CFSDS cumulative area for all six cases.

## Result

- median day-1 area ratio: **1.07x**;
- every case is already >2x by **day 2**;
- median final ratio: **12.07x** at radius 2 and **11.90x** at radius 1;
- all six remain >2x at both radii.

## Diagnosis

The initial growth is approximately correct. The failure is **late/continued growth**: the model
keeps expanding after the observed fire has effectively stopped. Neighbor radius is not the
cause.

The remaining structural candidates are:

1. missing containment/stopping;
2. event-timing mismatch between daily perimeters and hourly weather;
3. excessive daily weather/FFMC-driven growth.

No calibration multiplier was applied. P164.3 remains paused.

## Next

The next phase should add a **containment/stopping** mechanism or verify the weather/FFMC
sequence before any model tuning. A global multiplier would hide the late-growth error.

## Limits

- Six cases, one fuel/terrain tile.
- Reanalysis weather and daily perimeters.
- Reconstructed ignition.
- Daily snapshots use a fixed 13:00 start.

## Verification

- Dashboard: GREEN.
- Snapshot and radius tests green.
- Trajectory diagnostic reproducible.
- No merge without maintainer approval.
