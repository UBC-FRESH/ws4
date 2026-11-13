# P185 close-out: Predictive Ecology benchmarks and LANDIS kernel

Date: 2026-11-13
Phase: P185 (#1094)
Branch: `feature/p185-landis-benchmarks`
Tasks: P185.1 (#1095), P185.2 (#1096), P185.3 (#1097), P185.4 (#1098)
Design note: `notes/design/ws4-predictive-ecology-benchmarks.md`
Registry: `notes/reports/p185-benchmark-registry.json`

## Result

P185 adds a provenance-complete Predictive Ecology benchmark registry and an original
LANDIS-II-compatible succession kernel with exact reference tests.

## What changed

- A registry of Predictive Ecology repositories, commits, licence status, exact test files,
  distributional tests, and observed-data protocols.
- `ws4/ecosystem/landis.py`: site biomass, competition, ANPP, developmental mortality, and
  age mortality from the published LANDIS-II Biomass Succession equations.
- Exact reference tests from `Biomass_core` for ANPP, growth/mortality, competition, and
  `sumB`, including spin-up and non-spin-up stages.
- Docs: `docs/reference/ecosystem-landis.rst`.

## Evidence

- LANDIS kernel tests: 6 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Exact ANPP, growth/mortality, competition, and sumB reference values match.
- The young-cohort `sumB` regression and age-zero boundaries are covered.

## Benchmark layers

- **Exact**: LANDIS kernel reference values.
- **Model-to-model**: `Biomass_core` versus LANDIS-II Biomass Succession (manual reports
  mean differences around 0.03–0.05%).
- **Distributional**: `scfm` ignition/escape/spread diagnostics; `LandMine` fire-size/FRI/
  reburn invariants.
- **Observed data**: `Biomass_validationKNN` MAD/SNLL protocol.
- **Event perimeters**: P157 Dogrib remains separate.

## Limits

- The LANDIS kernel is not yet wired into the P180 succession process.
- Most source modules have no explicit licence file; they are reference-only.
- No third-party code or prose is copied.
- `fireProperties` and `Biomass_fuels` are weak numerical benchmarks.
- `LandMine` is not a full parity test of its original.
- `scfm` validates fire-regime distributions, not event perimeters.
- Age mortality has a property test, not the full published numeric table.

## Recommendation

Next: wire the LANDIS kernel into a `LandisSuccessionProcess` and compare a WS4 cohort
succession run to an LBSE-style integration case. Then add the `scfm`/`LandMine` distributional
diagnostics as a separate fire-regime benchmark.

## Pull request

PR: #1099 is queued for maintainer approval. Do not merge without approval.
