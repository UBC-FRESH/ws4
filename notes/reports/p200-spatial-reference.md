# P200 report: small spatial Biomass_core landscape

Date: 2026-11-14
Phase: P200 (#1180)
Branch: `feature/p200-spatial-landscape`
Design note: `notes/design/ws4-spatial-landscape.md`

## Result

The full Biomass_core module ran on a 10 × 10 spatial landscape for 10 years and produced a
deterministic trajectory. This is the first spatial reference captured with the open-source
R/SpaDES stack.

## Case

- 100 pixels, 100 m resolution;
- one ecoregion;
- two species (`Pice_Gla`, `Popu_Tre`);
- two pixel groups, two cohorts each;
- 10-year horizon, 10-year succession timestep;
- fixed seed `20261114`.

## Captured output

`tests/fixtures/landis_spatial_reference/simulationOutput.csv`:

| Year | N pixels | Biomass | ANPP | Mortality | Regeneration |
| --- | --- | --- | --- | --- | --- |
| 0 | 100 | 2000 | 0 | 0 | 0 |
| 0 | 100 | 2694 | 762 | 66 | 0 |
| 10 | 100 | 9460 | 920 | 294 | 2 |

Two independent runs with the fixed seed produced byte-identical CSV output.

## Evidence

- Reproducibility script: `scripts/landis_spatial_reference.R`.
- Fixture contract test: `tests/test_landis_spatial_reference.py` (1 passed).
- Runtime: R 4.3.3, LandR 1.2.0.9064, SpaDES.core 3.2.1.9067, Biomass_core
  `21b3392324c2787a47751be808cbf9e595f308c0`.
- The optional `LandR.CS` package was absent; it produced a warning, not a failure.

## Boundaries

- Hand-built toy landscape, not a real forest.
- No downloaded species layers, climate modifiers, fire, insects, or management.
- No WS4-vs-reference trajectory comparison yet.
- Not an observed-data validation.

## Next

Run the WS4 LANDIS process on the same initial cohorts and compare the 10-year trajectory. That
is the first WS4-vs-Biomass_core spatial comparison.
