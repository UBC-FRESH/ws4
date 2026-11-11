# P168 close-out: start-perimeter event benchmark

Date: 2026-11-11
Phase: P168 (#1001)
Branch: `feature/p168-start-perimeter`
Pull request: #1005

## Outcome

Implemented first-perimeter seeding in `run_observed_case` and reran the six P167 cases.

## Result

- median IoU: **0.095**;
- best IoU: **0.097**;
- worst IoU: **0.079**;
- area bias range: **+8.77x to +11.60x**;
- all six still overpredicted.

First-perimeter seeding did not fix the bias. In one case it made overlap slightly worse.

## Decision

Point ignition was a protocol flaw, but it is not the dominant cause. The model fills large
connected burnable areas while observed fires stop far short. The next diagnosis should test:

- containment/stopping;
- observed growth timing;
- fuel/weather scale;
- growth-kernel area scaling.

No calibration multiplier was applied. P164.3 remains paused.

## Limits

- Six cases, one fuel/terrain tile.
- Reanalysis weather and daily perimeters.
- Reconstructed ignition.
- No station-observed hourly cases.

## Verification

- Dashboard: GREEN.
- First-perimeter tests green.
- Six-case rerun reproducible.
- No merge without maintainer approval.
