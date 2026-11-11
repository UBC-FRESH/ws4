# P175 close-out: ROS-scale sensitivity

Date: 2026-11-11
Phase: P175 (#1036)
Branch: `feature/p175-ros-scale`
Pull request: queued for maintainer approval

## Outcome

Added a head-ROS multiplier diagnostic and ran two 100 m large cases at 1.0, 0.75, 0.5, and
0.25.

## Result

- final area and IoU are unchanged across all multipliers;
- both cases fill the burnable basin even at 0.25x ROS;
- the residual is not a uniform ROS-scale error.

## Decision

P175 is complete. Do not change default ROS. Implement containment/stopping or a defensible
burnable-area limit. No calibration was applied. P164.3 remains paused.

## Limits

- Two large fires at 100 m.
- Reanalysis weather and daily perimeters.
- The multiplier only changes crown ROS in the current kernel.
- Burnable area is set by the FireSTARR fuel map.

## Verification

- Dashboard: GREEN.
- ROS multiplier test green.
- Eight sensitivity runs reproducible.
- No merge without maintainer approval.
