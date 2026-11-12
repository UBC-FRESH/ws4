# P179 close-out: generic process executor

Date: 2026-11-12
Phase: P179 (#1056)
Branch: `feature/p179-process-executor`
Tasks: P179.1 (#1057), P179.2 (#1058), P179.3 (#1059), P179.4 (#1060)
Design note: `notes/design/ws4-process-executor.md`

## Result

P179 turns the P144 stochastic engine from a fire-specific runner into a generic
multi-process executor. Fire and salvage are now sources behind one protocol; a synthetic
mutating process proves the executor is not fire-shaped.

## What changed

- `ws4/ecosystem/process.py`: `Process`, `DecisionSource`, `ProcessContext`, declaration
  validation, and duplicate-id checks.
- `ws4/ecosystem/executor.py`: one annual executor over `EVENT_PHASES`, event ownership,
  year/phase/scenario checks, canonical ordering, repeat-until-empty batches, event and year
  observers, and the existing event log.
- `ws4/ecosystem/fire.py`: `FireProcessSource` and `SalvageProcessSource`; `FireRun` now uses
  `Executor` while preserving `FireResult`, the event log, and accounts.
- Tests: protocol validation, two-source ordering, replay equality, foreign-owner rejection,
  fire + synthetic + salvage in one run, and the existing fire suite.
- Docs: `docs/reference/ecosystem-process.rst`; index and design note.

## Evidence

- Ecosystem/fire/process/executor tests: 26 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Existing fire event-log and account tests pass through the executor.
- The synthetic process changes cohort fuel in the same run as fire and salvage.

## Decision

The executor is now the engine seam. Fire is one source, not the loop.

## Limits

- Same-phase sources are asked in declaration order; each batch is canonically sorted.
- State read/write declarations are validated as names, not enforced as exclusive ownership.
  Fire and salvage share the snag variable by design.
- The executor is annual, not continuous time.
- The synthetic process is a test source, not a production succession model.
- No new fire physics, calibration, or optimizer integration.

## Next

P180: succession, regeneration, and the calibrated yield bridge. The executor is the
prerequisite.

## Pull request

PR: #1061 is queued for maintainer approval. Do not merge without approval.
