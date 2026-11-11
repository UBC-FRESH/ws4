# P167 close-out: reanalysis event benchmark

Date: 2026-11-11
Phase: P167 (#996)
Branch: `feature/p167-reanalysis-benchmark`
Pull request: queued for maintainer approval

## Outcome

P167 ran six independent CFSDS cases with one uncalibrated protocol:

- P166 `2003_526`;
- `2003_706`;
- `2009_147`;
- `2009_79`;
- `2023_19`;
- `2023_786`.

## Distribution

- median IoU: **0.096**;
- best IoU: **0.127**;
- worst IoU: **0.079**;
- median area bias: **+9.25x**;
- area bias range: **+6.68x to +11.60x**;
- overpredicted cases: **6 of 6**.

The P166 overprediction is not an outlier. It is systematic across years, sizes, and fuel codes.

## Decision

P167 is complete as a **systematic overprediction benchmark**.

Do not tune a global multiplier to these six cases. The next step is a process diagnosis of scale
and shape: ignition/start-area treatment, daily versus hourly perimeter timing, fuel/weather
representativeness, and the growth kernel's area scaling.

P164.3 remains paused.

## Limits

- Six cases, one fuel/terrain tile.
- Reanalysis weather, not on-site stations.
- Daily satellite perimeters.
- Reconstructed ignition.
- No treatment or burn-probability evidence.

## Verification

- Dashboard: GREEN.
- Six fixtures load.
- Benchmark runner is reproducible.
- No merge without maintainer approval.
