# Process-conditioned schedule evaluation

Status: implemented (P190)
Phase: P190 (#1125)
Date: 2026-11-13
Related: `notes/design/ws4-stochastic-landscape.md`, `docs/reference/ecosystem-ensemble.rst`

## 1. Purpose

The optimizer still evaluates account overlays. P190 is the first bridge from a block-level
schedule decision to the process engine: it maps blocks to fragments, runs the annual
fire/succession/regeneration/management processes, and returns a replayable final state and a
final account table.

It is an evaluation path, not a replacement for the optimizer search loop.

## 2. Inputs

`evaluate_process_schedule` takes:

- an initial `CohortState` and landscape edges;
- a block schedule and block-to-fragment mapping;
- a horizon, fire configuration, optional succession/regeneration sources;
- an optional process override, such as `LandisSuccessionProcess`;
- a harvest fraction, scenario id, and seed.

The schedule and mapping are validated by `ScheduleSource`. Invalid blocks, missing fragment
mappings, negative horizons, negative seeds, and empty scenario ids fail loudly.

## 3. Outputs

`ProcessScheduleEvaluation` exposes:

- final cohort state;
- replayable event log;
- per-year process values;
- final accounts;
- a stable JSON summary;
- `write`, which emits values, accounts, and the summary.

Final accounts include:

- `state.biomass_t`, `state.fuel_t`, `state.snag_t`;
- `bridge.volume_m3`;
- `fire.burned_area_ha_total` and `fire.count_total`;
- `harvest.count_total` and `harvest.area_ha_total`;
- `salvage.count_total` and `regeneration.count_total`.

Harvest area is the area of the distinct fragments touched, not a sum of repeated treatments.

## 4. Exact test result

`tests/test_ecosystem_evaluation.py` uses a 3 × 3 grid of 10 ha fragments, a fire-free
configuration, one clearcut on block 1 covering fragments 1 and 2, and a one-year horizon:

- harvest events: 2;
- harvest area: 20 ha;
- final biomass below the 9000 t initial total;
- area conserved;
- harvested final biomass below the no-harvest baseline;
- the same seed and schedule produce the same summary and replay token.

## 5. Limits

- The final account table is a reporting view, not the compiled management contract.
- The volume bridge is provisional and uncalibrated.
- The evaluator does not search schedules or feed the optimizer objective yet.
- Harvest is the simplified clearcut-like bridge, not full treatment semantics.
- Fire and succession results remain process-model outputs, not observed validation.
