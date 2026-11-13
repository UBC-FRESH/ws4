# P184 close-out: schedule-to-ecosystem management bridge

Date: 2026-11-13
Phase: P184 (#1087)
Branch: `feature/p184-management-bridge`
Tasks: P184.1 (#1088), P184.2 (#1089), P184.3 (#1090), P184.4 (#1091)
Design note: `notes/design/ws4-management-bridge.md`

## Result

A block-level schedule can now be mapped to fragments and applied to the ecological cohort
state before later succession, fire, and regeneration.

## What changed

- `ws4/ecosystem/management.py`: schedule loader, block/fragment mapping loader, and
  `ScheduleSource`.
- Harvest transition: remove a cohort fraction, create a bare age-zero cohort, conserve area.
- `ProcessEnsembleConfig.management`: optional controlled source in the treatment phase.
- API exports, docs, design note, and tests.

## Evidence

- Management tests: 6 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Harvest events occur at the scheduled offset.
- Area is conserved after harvest.
- Harvested and unharvested runs differ in final biomass/fuel.
- Replay and CRN tests remain green.

## Simplified semantics

This is a clearcut-like bridge:

- removes `area_fraction × harvest_fraction` from every live cohort;
- creates bare age-zero cohorts for removed area;
- no retention trees;
- no product curves or merchantable volume;
- no treatment-specific track transition;
- no fragment-specific silviculture beyond the removed fraction.

## Limits

- The schedule is block-level with an explicit fragment mapping.
- No optimizer coupling yet; this is an outside-loop process bridge.
- The volume bridge remains provisional.
- Fire/succession still run on the standalone process state.

## Next

Wire the management-conditioned process ensemble into a high-fidelity elite evaluation or an
estate-state adapter. The compiled treatment semantics remain the reference.

## Pull request

PR: #1092 is queued for maintainer approval. Do not merge without approval.
