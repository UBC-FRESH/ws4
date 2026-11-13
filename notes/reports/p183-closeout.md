# P183 close-out: process-driven scenario ensemble

Date: 2026-11-13
Phase: P183 (#1081)
Branch: `feature/p183-process-ensemble`
Tasks: P183.1 (#1082), P183.2 (#1083), P183.3 (#1084), P183.4 (#1085)
Design note: `notes/design/ws4-process-ensemble.md`

## Result

The process engine can now run as a scenario ensemble outside the optimizer, producing per-year
account-like metrics and optional risk aggregation.

## What changed

- `ws4/ecosystem/ensemble.py`: process metrics, one scenario runner, and a scenario ensemble.
- Metrics: fire count/area/mortality, succession/salvage/regeneration counts, state biomass/fuel/
  snag, and bridge volume.
- `run_process_ensemble`: one executor per scenario seed, scenario column, risk aggregation.
- `ProcessEnsembleResult.write`: values, aggregated rows, and summary.
- API exports, docs, design note, and tests.

## Evidence

- Ensemble tests: 5 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Replay produces the same event log and values.
- Two configurations with the same seed share fire ignition draws.
- Risk aggregation produces `risk.*` pseudo-accounts.

## Boundary

This is process-driven, but it is not yet schedule-conditioned:

- the process state is standalone;
- a harvest schedule does not change fuel before the process runs;
- there is no management/state bridge back into the compiled dataset;
- the optimizer still uses the P181 account overlay in its inner loop.

That missing management bridge is the next integration step.

## Limits

- Annual, fragment-level processes.
- No schedule-conditioned fuel or treatment effects.
- The volume bridge remains provisional.
- Scenario overrides only choose the seed; process parameter overrides are not applied yet.

## Recommendation

Keep this as the outside-loop process ensemble. The next phase should add a management/state
bridge or a high-fidelity elite evaluation that uses it, not another account overlay.

## Pull request

Merged as `4419743` (PR #1086); branch deleted.
