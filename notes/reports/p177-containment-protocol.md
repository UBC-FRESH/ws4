# P177 containment contract and validation protocol

Date: 2026-11-11
Phase: P177 (#1046)
Task: P177.2 (#1048)

## Containment contract

`run_observed_case` now accepts an optional boolean `containment_mask`.

- `False` cells are normal fuel.
- `True` cells are contained/non-burnable, such as a firebreak or suppression line.
- The default is `None`, which preserves free-burn behavior.
- The mask must match the observed grid and must leave burnable cells.
- The mask is a management scenario input. It is not fitted to the cases.

Tests cover a containment block, shape mismatch, and a fully contained grid.

## Validation protocol

P176 showed that the model fills the burnable basin:

- median simulated area / basin: 0.995;
- median observed area / basin: 0.130;
- 8 of 12 simulations fill at least 95% of the basin.

That means the small CFSDS cases are suppression-dominated. They are not valid ROS-skill
evidence.

Use:

- **Free-burn/large fires** for ROS and event skill.
- **Small/suppressed fires** for potential-growth or containment-scenario work only.
- **Containment masks** for management scenarios, not model calibration.

## Decision

Small-fire perimeter mismatch is not a reason to tune ROS. The model needs an explicit
containment scenario or a defensible burnable-area constraint. P164.3 remains paused until the
validation protocol is applied to free-burn evidence.
