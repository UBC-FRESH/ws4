# Phase close-out report: P82 Seeded max-flow

Phase: P82, Seeded max-flow
Parent issue: #575
Pull request: to be opened
Date: 2026-10-29
Status: ready for review. Not merged.

## What changed

- `max_flow` now accepts `--initial-schedule` and `--flow-reference-period`.
- Flow feasibility uses the requested reference period instead of always the final period.
- The c5 README uses `seed_200y.csv`, first-period reference, and ±5% flow.

## Result

A seeded 100-iteration probe produced floor-feasible solutions at 500k, 250k, 125k, and
62.5k conifer, but **no probe satisfied even flow**. The worst change against period 1
was about **-56%**. The advisory ceiling for the flow condition is **0**. A
1,000-iteration probe timed out.

This is a negative result, not a certified maximum. The base scenario remains a soft
goal-programming scenario with seeded harvest; the stock target remains soft tension.

## Gates

All seven gates green: lint 0.11 s, format 0.11 s, types 10.10 s, tests 144.71 s, validator 0.92 s, docs 16.63 s, docstrings 2.84 s.
