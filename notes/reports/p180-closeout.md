# P180 close-out: succession, regeneration, and the yield bridge

Date: 2026-11-12
Phase: P180 (#1062)
Branch: `feature/p180-succession-yield`
Tasks: P180.1 (#1063), P180.2 (#1064), P180.3 (#1065), P180.4 (#1066)
Design note: `notes/design/ws4-succession-yield.md`

## Result

P180 adds the first living ecological processes to the P179 executor and a provisional
species-biomass-to-volume bridge.

## What changed

- `ws4/ecosystem/succession.py`: deterministic cohort aging, logistic biomass growth, fuel
  accumulation, and snag decay with explicit species parameters.
- `ws4/ecosystem/regeneration.py`: tape-seeded juvenile establishment without changing area
  fractions.
- `ws4/ecosystem/bridge.py`: `SpeciesVolumeBridge`, a provisional biomass-to-volume table with
  species rates, a default rate, a merchantable fraction, and versioned parameters.
- `tests/test_ecosystem_succession_integration.py`: fire, succession, salvage, regeneration,
  and the bridge share one executor run.
- Docs: `docs/reference/ecosystem-succession.rst`; design note.

## Evidence

- Ecosystem succession/regeneration/bridge/integration tests: 14 passed.
- Ecosystem fire/executor/process tests: 26 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- The integration test checks area conservation and non-negative bridge volume.
- Replay tests pass for succession and regeneration.

## Calibration boundary

The yield bridge is **provisional**, not calibrated. Its coefficients are explicit defaults;
`VolumeBridgeConfig` records `calibration_status: provisional` and a provenance note. It does
not modify the compiled management dataset or its yield curves. A future calibration phase
must pre-register data, bounds, and a holdout before fitting.

The succession and regeneration parameters are likewise provisional planning values, not
observed-stand calibrations.

## Limits

- Single-cohort juvenile establishment, not species competition.
- No disturbance interactions beyond fire mortality.
- Annual, fragment-level processes.
- The bridge is an ecological view, not a replacement for the compiled yield curves.
- No estate optimizer integration or policy search.

## Next

P181: wire scenario/risk evaluation into the estate optimizer. P179 and P180 must merge first.

## Pull request

PR: #1067 is queued for maintainer approval. Do not merge without approval.
