# Process-driven scenario ensembles

Status: implemented (P183)
Phase: P183 (#1081)
Date: 2026-11-13
Related: `notes/design/ws4-process-executor.md`,
`notes/design/ws4-risk-optimization.md`, `ws4/ecosystem/ensemble.py`

## 1. Purpose

P181 adds a fast account-overlay risk path. P183 runs the actual process engine outside the
optimizer: fire, succession, salvage, regeneration, and the bridge, one executor per scenario
seed. It produces per-year, account-like metrics and optionally risk-aggregates them.

## 2. Account metrics

Each year observes:

- `fire.count`, `fire.burned_area_ha`, `fire.mortality_area_ha`;
- `succession.count`, `salvage.count`, `regeneration.count`;
- `state.biomass_t`, `state.fuel_t`, `state.snag_t`;
- `bridge.volume_m3`.

The metrics come from the event log and the state, not from hard-coded process assumptions.

## 3. Scenario runner

`run_process_scenario` builds one executor for one scenario:

- fire source from the scenario tape;
- succession source;
- salvage source;
- regeneration source from the same tape;
- bridge observer.

`run_process_ensemble` runs every scenario in a `ScenarioSet`, stamps the scenario id, and
optionally calls `risk_account_values`. Common random numbers hold because each scenario seed
is fixed and the process draws are keyed by `(process, fragment, year, draw)`.

## 4. What this is not

This is not yet an estate-schedule risk model. The process state is not mapped back into the
compiled management dataset, and a treatment schedule does not change fuel before the fire
runs. The missing management/state bridge is the next integration step.

The P181 account-overlay path remains the optimizer's inner-loop risk path.

## 5. Validation

- One scenario produces a stable metric table.
- Ensemble output carries a scenario column and risk pseudo-accounts.
- Replaying a scenario seed reproduces the event log and values.
- Two configurations with the same seed share fire ignition draws.
- A bad horizon fails clearly.

## 6. Limits

- The process state is initial/standalone, not schedule-conditioned.
- No management bridge, salvage treatment schedule, or optimization coupling.
- Annual, fragment-level processes.
- The volume bridge remains provisional.
- Scenario overrides are not yet applied to process parameters beyond the seed.
