# P186 close-out: LANDIS succession process

Date: 2026-11-13
Phase: P186 (#1100)
Branch: `feature/p186-landis-process`
Tasks: P186.1 (#1101), P186.2 (#1102), P186.3 (#1103), P186.4 (#1104)
Design note: `notes/design/ws4-landis-succession-process.md`

## Result

The P185 LANDIS-II succession kernel now runs as a cohort-state process and can replace the
default logistic succession source in the P183 process ensemble.

## What changed

- `LandisSpeciesTraits` and `LandisSuccessionConfig`.
- `LandisSuccessionProcess`: one annual event per fragment.
- Kernel-driven biomass update from sumB, competition, ANPP, developmental mortality, and age
  mortality.
- Fuel and snag updates; area fractions unchanged.
- `ProcessEnsembleConfig.succession_process` override.
- API exports, docs, design note, and tests.

## Evidence

- LANDIS tests: 8 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- A two-year trajectory ages cohorts, keeps biomass within the species cap, and preserves
  area.
- The LANDIS event appears in the executor event log.
- The process runs through the scenario ensemble.

## Limits

- This is a single-cohort-table transition, not a full landscape LBSE integration.
- Seed dispersal, serotiny, resprouting, and light competition beyond the kernel are not
  implemented here.
- Species traits are provisional and not calibrated.
- The process does not yet feed the management yield curves or the estate optimizer.
- Fire and succession interactions remain simple.

## Next

Run a landscape-scale WS4-vs-LBSE comparison, then add the `scfm`/`LandMine` fire-regime
distributional benchmarks as a separate layer.

## Pull request

Merged as `296e26a` (PR #1105); branch deleted.
