# P190 close-out: process-conditioned schedule evaluation

Date: 2026-11-13
Phase: P190 (#1125)
Branch: `feature/p190-process-schedule-evaluation`
Tasks: P190.1 (#1126), P190.2 (#1127), P190.3 (#1128)
Design note: `notes/design/ws4-process-schedule-evaluation.md`

## Result

A block-level harvest schedule can now be evaluated through the process engine. The evaluator
returns a replayable final state, event log, per-year values, and a final account table. This is
the first schedule-decision bridge to the process layer, not an optimizer replacement.

## What changed

- `ws4/ecosystem/evaluation.py`:
  - schedule and block-to-fragment validation through `ScheduleSource`;
  - process run over fire, succession, regeneration, salvage, and management;
  - final state totals, provisional volume, fire totals, harvest counts/area, salvage and
    regeneration counts;
  - JSON summary and CSV artifact writer.
- Tests for harvest effects, baseline comparison, determinism, artifacts, zero horizon, and
  invalid inputs.
- Reference page and design note.

## Evidence

- Evaluation tests: 6 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- 3 × 3 grid of 10 ha fragments, fire-free, one clearcut on fragments 1 and 2:
  - harvest events **2**;
  - treated area **20 ha**;
  - final biomass below the 9000 t initial total;
  - area conserved;
  - harvested biomass below the no-harvest baseline;
  - same schedule and seed reproduce the same summary and replay token.

## Boundary

- The final account table is a reporting view; the compiled management dataset remains
  authoritative.
- The volume bridge is provisional and uncalibrated.
- The evaluator does not search schedules or feed the optimizer objective yet.
- Harvest remains the simplified clearcut-like bridge, not full treatment semantics.
- Fire and succession outputs are process-model results, not observed validation.

## Next

Add an objective adapter over the final evaluation accounts, then let the optimizer call the
process evaluator for candidate schedules. The landscape-scale WS4-vs-LBSE comparison remains
blocked without an R/SpaDES reference run or published numeric landscape output.

## Pull request

PR: #TBD is queued for maintainer approval. Do not merge without approval.
