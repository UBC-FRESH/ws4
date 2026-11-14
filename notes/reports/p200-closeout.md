# P200 close-out: small spatial Biomass_core landscape reference

Date: 2026-11-14
Phase: P200 (#1180)
Branch: `feature/p200-spatial-landscape`
Tasks: P200.1 (#1181), P200.2 (#1182), P200.3 (#1183)
Design note: `notes/design/ws4-spatial-landscape.md`
Report: `notes/reports/p200-spatial-reference.md`

## Result

The full Biomass_core module was executed on a small spatial landscape and produced a
deterministic 10-year trajectory. The reproducibility script and captured fixture are on the
branch.

## What changed

- `scripts/landis_spatial_reference.R`:
  - 10 × 10, 100 m landscape;
  - two species, two pixel groups, one ecoregion;
  - fixed seed `20261114`;
  - writes `simulationOutput.csv` and `sessionInfo.txt`.
- `tests/fixtures/landis_spatial_reference/` with the captured trajectory and provenance.
- `tests/test_landis_spatial_reference.py` with a stable fixture contract test.
- Design note, report, registry entry, and reference documentation.

## Evidence

- Spatial fixture test: 1 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Captured trajectory:
  - year 0: biomass 2000, ANPP 0, mortality 0, regeneration 0;
  - year 0 after init: biomass 2694, ANPP 762, mortality 66, regeneration 0;
  - year 10: biomass 9460, ANPP 920, mortality 294, regeneration 2.
- Two independent runs with seed `20261114` produced byte-identical CSV output.
- R 4.3.3, LandR 1.2.0.9064, SpaDES.core 3.2.1.9067, Biomass_core
  `21b3392324c2787a47751be808cbf9e595f308c0`.

## Boundary

- Hand-built toy landscape, not a real forest.
- No downloaded species layers, climate modifiers, fire, insects, or management.
- No WS4-vs-reference trajectory comparison yet.
- Not an observed-data validation.

## Next

Run the WS4 LANDIS process on the same initial cohorts and compare the 10-year trajectory. That
is the first WS4-vs-Biomass_core spatial comparison.

## Pull request

PR: #1184 is queued for maintainer approval. Do not merge without approval.
