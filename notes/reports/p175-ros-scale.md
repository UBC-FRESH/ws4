# P175 ROS-scale sensitivity

Date: 2026-11-11
Phase: P175 (#1036)
Task: P175.2 (#1038)
Manifest: `notes/reports/p175-ros-scale.json`
CSV: `notes/reports/p175-ros-scale.csv`

## Result

The final area is identical at head-ROS multipliers 1.0, 0.75, 0.5, and 0.25 for both 100 m
large cases.

| Case | 1.0x area bias | 0.75x | 0.5x | 0.25x |
| --- | ---: | ---: | ---: | ---: |
| 2003_96 | +3.67x | +3.67x | +3.67x | +3.67x |
| 2003_663 | +1.39x | +1.39x | +1.39x | +1.39x |

IoU is unchanged as well.

## Interpretation

Lowering ROS only delays arrival; it does not reduce final area within the event window. The
model is filling the connected burnable basin. The residual bias is therefore not a uniform ROS
scale error. It is a **stopping/containment** problem, or the burnable basin is too large relative
to the observed fire.

No multiplier is applied as calibration.

## Decision

Do not change the default ROS. Implement a containment/stopping mechanism or define a defensible
burnable-area constraint. P164.3 remains paused.
