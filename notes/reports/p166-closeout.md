# P166 close-out: hourly reanalysis depth case

Date: 2026-11-11
Phase: P166 (#991)
Branch: `feature/p166-reanalysis-depth-case`
Pull request: queued for maintainer approval

## Outcome

P166 adds one independent CFSDS event with hourly reanalysis weather:

- case `2003_526`;
- final observed scar 520 ha;
- 90 x 76 grid at 100 m;
- FireSTARR FBP fuel and terrain;
- Open-Meteo hourly reanalysis;
- reconstructed first-day ignition.

Contract decision: **depth-with-limit**, not fully ready.

## Model result

Uncalibrated, no multipliers:

- simulated area 5,325 ha vs observed 520 ha;
- area bias +924%;
- perimeter bias +496%;
- IoU 0.096;
- Sorensen 0.175;
- centroid distance 175 m;
- orientation error 21.6°.

The case is a clear overprediction failure. It is useful precisely because it is independent
and the failure is visible.

## What was added

- `scripts/build_cfsds_reanalysis_case.py` - reproducible fixture builder.
- `scripts/run_cfsds_reanalysis_case.py` - uncalibrated runner.
- `ws4/fire/observed.py` - `load_cfsds_reanalysis_case`.
- `tests/fixtures/fire/cfsds_2003_526` - derived fixture.
- tests for the fixture, loader, runner, and builder helpers.
- docs page for the case.

## Decision

P166 is complete as a **single depth-with-limit case with a poor uncalibrated result**.

The depth gate remains short of fully ready cases. P164.3 stays paused. The next meaningful
step is either:

1. add hourly station or higher-quality weather to this case; or
2. add more independent cases and report the distribution of this failure; or
3. diagnose the overprediction without tuning to this one fire.

Option 3 should not become a single-fire calibration exercise.

## Limits

- Reanalysis weather, not an on-site station.
- Daily satellite perimeters, not hourly observed perimeters.
- Reconstructed ignition.
- One case, one result.
- No treatment, burn-probability, or tree-mortality evidence.

## Verification

- Dashboard: GREEN.
- Fixture/loader tests: green.
- Runner and builder tests: green.
- No merge without maintainer approval.
