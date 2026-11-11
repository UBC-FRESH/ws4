# P174 close-out: large-fire resolution sensitivity

Date: 2026-11-11
Phase: P174 (#1031)
Branch: `feature/p174-resolution-sensitivity`
Pull request: #1035

## Outcome

Rebuilt two large cases at 100 m and reran the same uncalibrated first-perimeter protocol.

## Result

- `2003_96`: area bias 4.12x -> 3.67x; IoU 0.192 -> 0.209.
- `2003_663`: area bias 1.67x -> 1.39x; IoU 0.350 -> 0.387.

Resolution explains part of the large-fire bias, but a 1.4x-3.7x residual remains.

## Decision

P174 is complete. The residual large-fire bias is not a coarse-grid artifact. Next work should
audit residual ROS or add containment for small fires. No calibration was applied. P164.3
remains paused.

## Limits

- Two large cases.
- Reanalysis weather and daily perimeters.
- 100 m is finer but still not an hourly observed perimeter.
- No station-observed hourly case.

## Verification

- Dashboard: GREEN.
- Fine fixtures load.
- Benchmark reproducible.
- No merge without maintainer approval.
