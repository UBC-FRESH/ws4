# Greedy seeding: parallel floor mode and deadline

Date: 2026-10-29
Status: implemented and smoke-tested
Scope: `ws4.opt.seeding` and the optimizer's `--seed-greedy` path

## Problem

The 500-block carbon diagnostic with `--seed-greedy` spent 60 minutes in the seed phase
and executed zero iterations. Floor-mode seeding was serial, priced every candidate
chain through the carbon ledger at about 1.6 s each, and did not check the run deadline.
The projected scan was about 85 minutes for 3,093 chains.

## Change

- Floor-mode scoring now has the same fork-worker path as the reduction-goal mode.
  `--threads > 1` prices candidate chains across workers; results are ranked in the
  parent, so the schedule is deterministic.
- Both seed modes accept an absolute deadline and stop scoring/selection when it passes.
  A partial seed becomes the search's starting point instead of consuming the whole
  run budget.
- `Optimizer._solve` passes its existing deadline into `greedy_schedule`.

## Smoke test

500-block TSA46, high-displacement HWP, carbon cap 210,000 tCO2e, 25-minute limit,
8 seed workers, no initial schedule:

- seed completed with 51 CC blocks;
- 20/20 search iterations ran;
- wall time 17m17s, of which roughly 15–16 minutes was seeding;
- yield 325,362.73 m3 (below the 350k floor);
- cumulative emissions 52,045.54 tCO2e (cap met);
- exact replay: 51,886.24 tCO2e, still well below the cap;
- exact/ledger drift at offset 49 was 0.31% on cumulative emissions.

The seed is now deadline-safe and parallel, but it is still expensive. The 500-block
case spends most of a 25-minute run in seeding, and the seed stopped at 51 blocks because
the carbon ceiling bound before the yield floor. The next step is cheaper seed scoring
(shortlist or batched contributions), not more deadline plumbing.

## Verification

- `tests/test_seeding.py`: 8 passed, including a deadline test and a serial/parallel
  floor-seed equivalence test.
- `python scripts/dashboard.py`: GREEN on all seven gates.
