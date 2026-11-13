# P189 close-out: LANDIS reference traits and exact age mortality

Date: 2026-11-13
Phase: P189 (#1120)
Branch: `feature/p189-landis-reference-traits`
Tasks: P189.1 (#1121), P189.2 (#1122), P189.3 (#1123)
Design note: `notes/design/ws4-landis-reference-traits.md`

## Result

The LANDIS kernel now has published reference traits for 16 species and exact age-mortality
reference rows for both spin-up and non-spin-up stages. The previous trait values were
provisional.

## What changed

- `LANDIS_REFERENCE_TRAITS`: 16-species maxB, maxANPP, longevity, mortality shape, and
  growth-curve values from the public Biomass_core appendix tables.
- `landis_reference_config`: validated selection of reference species and stage.
- Exact age-mortality tests at ages 2, 3, 4, 5, 10, 20, 50, 100, 200, 300, and 400.
- Trait-provenance documentation and benchmark-registry update.

## Evidence

- LANDIS tests: 11 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Reference trait examples:
  - `abiebals`: maxB 26580, maxANPP 886, longevity 200;
  - `pinustro`: maxB 38150, maxANPP 1090, longevity 400;
  - `tsugcana`: maxB 32880, maxANPP 1096, longevity 500.
- Age-mortality examples:
  - spin-up age 2, B 1096: mAge 1.15;
  - spin-up age 100, B 27418: mAge 36.62;
  - spin-up age 400, B 3915: mAge 533.75;
  - non-spin-up age 2, B 1096: mAge 0.05;
  - non-spin-up age 300, B 21260: mAge 389.39;
  - non-spin-up age 400, B 3954: mAge 535.12.

## Boundary

- No LBSE or LandR run; this is a kernel-level reference comparison.
- Fuel fraction and snag decay are not in the appendix and remain provisional.
- Dispersal, serotiny, resprouting, and light competition remain unimplemented.
- The traits are one ecoregion's appendix values, not a universal parameter set.

## Next

Wire the reference configuration into the process-ensemble report, then address the remaining
process-to-management/optimizer bridge. The landscape-scale WS4-vs-LBSE comparison remains
blocked without an R/SpaDES reference run or published numeric landscape output.

## Pull request

PR: #TBD is queued for maintainer approval. Do not merge without approval.
