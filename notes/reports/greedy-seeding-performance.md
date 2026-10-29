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

| Candidate policy | Seed chains | Wall time | Seed phase | Search |
| --- | ---: | ---: | ---: | ---: |
| all chains (before) | 3,093 | 17m17s | ~15–16 min | 20 iterations |
| top 1 per block (capped) | 500 | 4m06s | ~3m27s | 20 iterations |
| top 1 per block + stand-state cache | 500 unique states pre-priced | **1m58s** | ~1m | 20 iterations |

- The capped seed produced exactly the same 51-block schedule as the exhaustive seed,
  so the cap cost no quality here.
- The stand-state cache prices 319 `(track, age)` states and the reachable chain states
  once; the seed then reads cached per-hectare accounts instead of rerunning CBM per
  block in each fork worker.
- Yield 325,362.73 m3 (below the 350k floor);
- cumulative emissions 52,045.54 tCO2e (cap met);
- exact replay: 51,886.24 tCO2e, still well below the cap;
- exact/ledger drift at offset 49 was 0.31% on cumulative emissions.

The cap is the important fix: 3,093 full 50-year ledgers for a starting schedule was
never justified. The seed is now 4 minutes end-to-end on the 500-block case, with
identical selected blocks. If a wider shortlist is ever needed, `--seed-candidates`
raises the cap explicitly; batched scoring remains the longer-term improvement.

## Verification

- `tests/test_seeding.py`: 8 passed, including a deadline test and a serial/parallel
  floor-seed equivalence test.
- `python scripts/dashboard.py`: GREEN on all seven gates.
