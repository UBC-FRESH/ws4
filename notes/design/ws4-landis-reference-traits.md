# LANDIS reference traits and exact age mortality

Status: implemented (P189)
Phase: P189 (#1120)
Date: 2026-11-13
Related: `notes/design/ws4-predictive-ecology-benchmarks.md`,
`docs/reference/ecosystem-landis.rst`

## 1. Purpose

P185/P186 implemented the LANDIS-II Biomass Succession kernel with provisional species traits.
P189 replaces the provisional biomass and productivity values with the published
``Biomass_core`` appendix values where they exist, and closes the missing exact age-mortality
reference test.

## 2. Reference traits

`LANDIS_REFERENCE_TRAITS` contains the 16 species in the appendix:

- maximum cohort biomass (`maxB`);
- maximum ANPP (`maxANPP`);
- longevity;
- mortality shape;
- growth-curve exponent.

The source is the public `Biomass_core` appendix comparison table
`LBSE_LandR_comparisonTables.xlsx`, tables 6 and 9. The values are numeric reference facts;
no third-party code or prose is copied.

Fuel fraction and snag decay are not in those tables, so they stay at the provisional
`LandisSpeciesTraits` defaults. That boundary is explicit: the reference table covers the
growth kernel, not fuel or snag dynamics.

## 3. Reference configuration

`landis_reference_config(species=None, stage="nonSpinup")` returns a
`LandisSuccessionConfig` with the selected reference traits. `None` selects all 16 species.
Unknown names, a bare string, and an invalid stage fail loudly. Species outside the reference
table still receive the provisional default traits.

## 4. Exact age mortality

`calculate_age_mortality` is checked against the public `Biomass_core`
`test-calculateAgeMortality.R` table at ages 2, 3, 4, 5, 10, 20, 50, 100, 200, 300, and 400,
for both spin-up and non-spin-up stages, using a longevity of 500 and a mortality shape of 10.

The spin-up case includes the 0.001 annual spin-up mortality fraction. The reference values
are rounded to two decimals; the test tolerance is 0.01.

Selected expected values:

- spin-up age 2, B 1096: `mAge` 1.15;
- spin-up age 100, B 27418: `mAge` 36.62;
- spin-up age 400, B 3915: `mAge` 533.75;
- non-spin-up age 2, B 1096: `mAge` 0.05;
- non-spin-up age 300, B 21260: `mAge` 389.39;
- non-spin-up age 400, B 3954: `mAge` 535.12.

## 5. Limits

- No LBSE or LandR run; this is a kernel-level reference comparison.
- Dispersal, serotiny, resprouting, and light competition remain unimplemented.
- Fuel fraction and snag decay remain provisional.
- The reference traits are one ecoregion's appendix values, not a universal parameter set.
