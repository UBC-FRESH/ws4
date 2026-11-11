# P172 close-out: fuel sensitivity

Date: 2026-11-11
Phase: P172 (#1021)
Branch: `feature/p172-fuel-sensitivity`
Pull request: queued for maintainer approval

## Outcome

Added a homogeneous-fuel diagnostic and compared per-cell fuel with the dominant burnable fuel.

## Result

- median per-cell area ratio: 10.35x;
- median homogeneous-dominant area ratio: 10.25x;
- homogeneous fuel reduced the ratio in 2 of 6 cases, only slightly;
- IoU changed little.

Fuel heterogeneity is not the cause.

## Decision

P172 is a negative fuel result. The remaining explanations are suppression/containment or a
genuine ROS-scale issue. No calibration was applied. P164.3 remains paused.

## Limits

- Six small fires in one fuel/terrain tile.
- Reanalysis weather and daily perimeters.
- Homogeneous override uses default blend parameters.
- Small fires are likely suppression-dominated.

## Verification

- Dashboard: GREEN.
- Fuel-override and diagnostic tests green.
- No merge without maintainer approval.
