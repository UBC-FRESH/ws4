# Schedule-to-ecosystem management bridge

Status: implemented (P184)
Phase: P184 (#1087)
Date: 2026-11-13
Related: `notes/design/ws4-process-ensemble.md`,
`ws4/ecosystem/management.py`, `ws4/ecosystem/ensemble.py`

## 1. Purpose

P183 runs the process engine outside the optimizer, but the ecosystem state is standalone. P184
adds the first management bridge: a block-level schedule is mapped to fragments, harvest events
are emitted in the treatment phase, and the cohort state is changed before later succession,
fire, and regeneration.

## 2. Inputs

- `load_schedule`: `block_id,treatment,offset` CSV.
- `load_block_fragments`: `block_id,fragment_id` CSV.
- `ScheduleSource`: typed schedule, mapping, harvest fraction, and scenario id.

The schedule offset is the annual executor year. Unknown blocks, duplicate events, duplicate
mapping rows, and invalid ids fail closed.

## 3. Harvest transition

For each scheduled fragment, `ScheduleSource.apply`:

- removes `area_fraction × harvest_fraction` from every live cohort;
- keeps the survivor fraction in the original cohort;
- creates a bare age-zero cohort for each removed fraction, with the same species and zero
  biomass/fuel/snag;
- preserves total fragment area.

This is a **clearcut-like** bridge. It does not implement retention trees, product curves,
treatment-specific track changes, or the compiled dataset's full treatment semantics.

## 4. Integration

`ProcessEnsembleConfig.management` accepts a `DecisionSource`. The ensemble inserts it in the
treatment phase before salvage. A harvested landscape therefore has lower live biomass and fuel
when succession, fire, and regeneration run.

## 5. Validation

- Schedule and mapping load reproducibly.
- Harvest events occur at the scheduled offset.
- Harvest conserves fragment area.
- Harvested and unharvested runs differ in final biomass/fuel.
- The existing replay and common-random-numbers tests still pass.

## 6. Limits

- Simplified clearcut/partial-removal semantics.
- No product volume, retention trees, or treatment-specific track transitions.
- The schedule is block-level; fragment mapping is an explicit input.
- No optimizer coupling yet; this is an outside-loop process bridge.
- The volume bridge remains provisional.
