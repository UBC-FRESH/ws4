# Phase close-out report: P80 C5 seeded even-flow

Phase: P80, C5 seeded even-flow
Parent issue: #565
Pull request: #567
Date: 2026-10-29
Status: merged and closed on 2026-10-29 as `e858db9`.

## What changed

- Added an oldest-first 200-year c5 seed (`examples/c5_base/seed_200y.csv`, installed in
  `scenarios/c5-base/seed_200y.csv`) with 7,253 scheduled blocks.
- Set both c5 flow targets to `flow_reference_period: 1` and ±5%, matching the working
  TSA27 pattern.
- Documented the MAI calculation:
  - area-weighted mean yield curves for managed conifer/deciduous;
  - MAI maximum at rotation age **112 years**;
  - managed THLB **71,138 ha**;
  - about **635 ha/year**, or **6,352 ha per 10-year period**.
- Ran a 100-iteration seeded run (`archive/c5-base-seeded-20261029`).
  - Most conifer/deciduous level targets are met.
  - The final growing-stock target remains below 23.9M; it is a soft goal-programming
    target, not a hard constraint.
- The seed lets the model carry wood through all 20 periods and makes the even-flow
  reference meaningful.

## Important correction

The previous base scenario had no seed and defaulted the even-flow reference to the
final period. That is why the max-flow probe returned zero: it was not the TSA27
experiment. This phase fixes the setup, not by claiming a max.

## Next

Run the seeded max-flow probe with `--initial-schedule` and `flow_reference_period: 1`
on the current `max_flow.py` branch. The current max-flow script does not yet accept an
initial schedule; that is the remaining tooling gap.
