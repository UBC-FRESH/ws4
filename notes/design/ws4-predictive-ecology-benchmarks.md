# Predictive Ecology benchmark registry and LANDIS succession kernel

Status: implemented (P185)
Phase: P185 (#1094)
Date: 2026-11-13
Related: `notes/design/ws4-succession-yield.md`,
`ws4/ecosystem/landis.py`, `notes/reports/p185-benchmark-registry.json`

## 1. Purpose

The Predictive Ecology / SpaDES ecosystem contains known implementations of LANDIS-II-style
succession and fire-regime processes. WS4 should use their published equations, tests, and
distributions as **reference oracles**, not copy their code or treat one model output as truth.

The registry records what is usable, at which evidence layer, and with which licence caveat.

## 2. Source inventory

| Module | Use | Layer |
| --- | --- | --- |
| `Biomass_core` | LANDIS-II Biomass Succession | Exact unit references; model-to-model LBSE comparison |
| `Biomass_regeneration` | Post-fire mortality, serotiny, resprouting | Logic and trait precedence |
| `Biomass_fuels` | LANDIS-II Dynamic Biomass Fuels | Fuel logic; thin tests |
| `scfm` | Fire ignition, escape, spread, regime calibration | Exact regime diagnostics; distributional calibration |
| `LandMine` | Boreal fire regime, fire sizes, FRI, reburn | Invariants and distributional checks |
| `Biomass_validationKNN` | Observed kNN biomass validation | Observed-data protocol (MAD/SNLL) |
| `fireProperties` | FBP fire properties | FBP interface logic; docs are a template |
| `LandR` | Module integration | Wiring and dependency structure |

Repository URLs and commits are in the JSON registry. Most modules have no explicit licence
file (`NOASSERTION`) or no licence field; `LandR` is GPL-3. The registry treats all of them as
reference material only.

## 3. LANDIS kernel

`ws4/ecosystem/landis.py` implements the published LANDIS-II Biomass Succession equations in
original Python:

- site biomass (`sumB`) with the two-year-before-succession boundary;
- competition indices `bAP` and `bPM`;
- actual ANPP;
- developmental mortality;
- age-related mortality.

The exact reference values from `Biomass_core` are used in
`tests/test_ecosystem_landis.py`. The tests cover spin-up and non-spin-up stages, age-zero
boundaries, the bAP > 1 branch, and the young-cohort `sumB` regression.

## 4. Evidence layers

1. **Exact equations**: exact published test values.
2. **Model-to-model**: `Biomass_core` versus LBSE; the manual reports mean biomass differences
   around 0.03–0.05%, with a small range.
3. **Distributional fire regime**: `scfm` ignition/escape/spread diagnostics and `LandMine`
   fire-size/FRI/reburn invariants.
4. **Observed data**: `Biomass_validationKNN` MAD/SNLL protocol.
5. **Event perimeters**: P157 Dogrib remains a separate layer.

## 5. Limits

- No third-party code is copied or vendored.
- The R/SpaDES modules are not runtime dependencies.
- `fireProperties` and `Biomass_fuels` are weak numerical benchmarks.
- `LandMine` is not a full parity test of its original.
- `scfm` validates regime distributions, not event perimeters.
- The WS4 kernel is not yet wired into the P180 succession process; P185 proves the equations
  and reference agreement first.
