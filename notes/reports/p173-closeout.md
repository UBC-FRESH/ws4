# P173 close-out: large-fire reanalysis benchmark

Date: 2026-11-11
Phase: P173 (#1026)
Branch: `feature/p173-large-fire-benchmark`
Pull request: #1030

## Outcome

Built four large-fire fixtures at 500 m and ran the same uncalibrated first-perimeter protocol.

## Result

- median large-fire IoU: 0.238;
- median large-fire area bias: 2.89x;
- best large-fire area bias: 1.67x;
- worst large-fire area bias: 4.12x;
- all four still overpredicted.

Small-fire comparison:

- median small-fire IoU: 0.096;
- median small-fire area bias: 10.35x.

The large-fire bias is far smaller. This supports small-fire suppression as a major cause, with
residual large-fire overprediction.

## Decision

P173 is complete. Add a containment/stopping mechanism for small fires, and audit the residual
large-fire ROS scale. No calibration was applied. P164.3 remains paused.

## Limits

- Four large fires at 500 m, one fuel/terrain tile.
- Reanalysis weather and daily perimeters.
- Reconstructed ignition.
- Coarse-grid evidence, not fine-scale validation.

## Verification

- Dashboard: GREEN.
- Four large fixtures load.
- Benchmark runner reproducible.
- No merge without maintainer approval.
