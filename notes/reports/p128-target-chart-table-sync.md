# P128 target chart table synchronization

Date: 2026-11-03
Status: complete; PR #796

## Root cause

The target chart updated `state.targets`, but the Plan table inputs retained
their old values. `Solve` calls `collectTargets`, which starts with
`state.targets` but then overwrites fields from the stale table inputs. An
all-period chart edit therefore reverted to the old target when Solve ran.

## Change

- Added `syncTargetTableInputs`.
- Every chart minimum/maximum edit now synchronizes the matching table inputs
  before marking the chart dirty.
- Solve therefore posts the chart-edited values.

## Verification

- All-period edit to 400,000:
  - Plan table period-1 input: `400000`
  - target POST period-1 level: `400000`
  - Solve body: `{"iterations":0,"patience":0,"time_limit":"00:05:00","seed":1,"years":50,"islands":1}`
- No implicit profile field.
