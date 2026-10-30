# TSA41 500-block carbon-aware optimization

Date: 2026-10-30
Status: bounded production subset complete; exact verification recorded
Scope: TSA41 500-block sample, CC-only schedule, public-default HWP, 50 years

Follow-up: the whole-schedule carbon evaluation in
`reports/carbon-tsa41-5k-optimization.md` reruns this case in 1m40s and reports
1,263,223 tCO2e exact at offset 49. The table below records the original per-state
run; the later batch run is the current path.

## Scope and caveat

This is a 500-block production subset (6,587 ha, 0.337% of TSA41), not the full
148,828-block landscape. It has 367 unique `(track, age)` states and 68 tracks.

A 5,000-block sample was built first, but the initial carbon-ledger evaluation consumed
the 20-minute budget before iteration 1. The 500-block sample is the practical bounded
optimization case.

The optimization uses a **CC-only** schedule. The production handoff schedule also has
`FIRE@20/40` events; the simulator treats those as no-ops (no `FIRE` treatment in the
matrix), and the carbon ledger's exact replay gap grew to 5.2% with them. Excluding fire
makes the ledger/exact comparison meaningful (0.9% at the target year).

## Setup

- Dataset: `ws4-tsa41-p120-matrix-fullschedule.dataset`
- Package: `femic-carbon-41-0e5b491e6a34`
- HWP: `config/carbon/hwp.bc.yaml` (public defaults)
- Initial schedule: 500 `CC@0` events
- Targets: managed yield 430,000–470,000 m3; minimize cumulative system emissions
- Search: SA, seed 1, 30 iterations, 8 carbon workers

## Result

| Metric | Baseline | Optimized | Change |
| --- | ---: | ---: | ---: |
| Scheduled blocks | 500 | **493** | -7 |
| Managed yield (m3) | 460,430 | **433,231** | -27,199 |
| Exact cumulative emissions @49 (tCO2e) | 1,281,211 | **1,258,901** | **-22,311 (-1.74%)** |
| Exact system carbon @49 (tC) | 1,136,807 | **1,142,969** | +6,163 |
| Exact HWP @49 (tC) | 71,815 | 70,725 | -1,089 |

The optimizer removed seven blocks and shifted eight CC events. The yield floor is met.
The emissions target was a zero ceiling used to drive minimization; it is not met.

Ledger vs exact at the target year:

- ledger cumulative emissions: 1,270,297.56
- exact cumulative emissions: 1,258,900.74
- ledger is **0.90% high**

The exact engine is the reported result.

## Reading

- On this bounded sample, carbon-aware optimization reduced exact cumulative emissions
  by **22.3 ktCO2e (1.74%)** while meeting a 430k m3 yield floor.
- System carbon rose slightly as well; the schedule moved harvest later/off a few
  blocks rather than simply reducing area.
- The 0.9% ledger/exact gap is small enough for search but not for reporting. Final
  schedules must use the exact `ws4 carbon` run.
- This is a mechanism result on 0.337% of TSA41, not a TSA41 production optimum. The
  full landscape needs a larger sample or a batched exact ledger, and the fire-event
  treatment needs a contract fix before it can be included.

## Artifacts

- `/tmp/opencode/tsa41-500-opt-cc-only/`
- `/tmp/opencode/tsa41-500-opt-cc-only-exact/`
- `/tmp/opencode/tsa41-500-cc-only-baseline-exact/`
- `/tmp/opencode/tsa41-5k-opt-min-emissions/` (0-iteration 5k attempt)
