# LANDIS succession process

Status: implemented (P186)
Phase: P186 (#1100)
Date: 2026-11-13
Related: `notes/design/ws4-predictive-ecology-benchmarks.md`,
`ws4/ecosystem/landis.py`, `ws4/ecosystem/ensemble.py`

## 1. Purpose

P185 proved the LANDIS-II Biomass Succession equations against exact reference values. P186
wires those equations into a cohort-state process and the P183 process ensemble.

## 2. Configuration

`LandisSpeciesTraits` carries:

- maximum cohort biomass (`max_b`);
- maximum ANPP (`max_anpp`);
- growth-curve exponent;
- age-mortality shape;
- longevity;
- fuel fraction;
- snag decay rate.

`LandisSuccessionConfig` carries species traits, a default, a succession time step, and the
spin-up/non-spin-up stage.

## 3. Transition

`LandisSuccessionProcess` runs in the `growth` phase and emits one event per fragment.
Applying the event:

1. maps the fragment cohort table to the kernel columns;
2. computes `sumB`;
3. computes competition `bAP` and `bPM`;
4. computes ANPP and developmental mortality;
5. computes age mortality;
6. updates biomass as `B + aNPPAct - mBio - mAge`, clipped to `[0, maxB]`;
7. increments age;
8. raises fuel to at least `biomass × fuel_fraction`;
9. decays snags.

Area fractions are unchanged. The event log records the transition.

## 4. Ensemble integration

`ProcessEnsembleConfig.succession_process` can replace the default logistic succession source.
The LANDIS process can therefore run with fire, salvage, regeneration, and management in the
same executor.

## 5. Validation

- Exact LANDIS kernel reference tests remain.
- A two-year trajectory ages cohorts and keeps biomass finite and capped.
- Area conservation is checked.
- The LANDIS event appears in the event log.
- The process runs through the P183 scenario runner.

## 6. Limits

- This is a single-cohort-table transition, not a full landscape LBSE integration.
- Seed dispersal, serotiny, resprouting, and light competition beyond the kernel are not
  implemented here.
- Species traits are provisional, not calibrated.
- The process does not yet feed management yield curves or the estate optimizer.
- Fire/succession interactions remain simple.
