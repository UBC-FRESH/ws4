LANDIS succession kernel
========================

Purpose
-------

``ws4.ecosystem.landis`` implements the published LANDIS-II Biomass Succession equations in
original Python. The Predictive Ecology ``Biomass_core`` tests are used as an exact reference
oracle; no third-party code is copied.

Functions
---------

- ``calculate_sum_b`` — site biomass with the LANDIS young-cohort boundary;
- ``calculate_competition`` — ``bAP`` and ``bPM``;
- ``calculate_anpp`` — actual ANPP;
- ``calculate_growth_mortality`` — developmental mortality;
- ``calculate_age_mortality`` — age-related mortality.

Reference traits
----------------

``LANDIS_REFERENCE_TRAITS`` holds the 16-species appendix values for maximum cohort biomass,
maximum ANPP, longevity, mortality shape, and growth-curve exponent. The values are numeric
reference facts from the public ``Biomass_core`` comparison tables; no third-party code or
prose is copied.

``landis_reference_config(species=None, stage="nonSpinup")`` returns a configuration with the
selected reference traits. Unknown names fail loudly. Fuel fraction and snag decay are not in
the appendix and remain provisional.

Process
-------

``LandisSuccessionProcess`` runs in the ``growth`` phase and applies the kernel to each
fragment. ``LandisSuccessionConfig`` supplies per-species traits and a default. The process
can replace the default logistic succession source through
``ProcessEnsembleConfig.succession_process``.

R parity
--------

P199 ran the published Biomass_core R kernel in an isolated LandR/SpaDES.core stack and captured
randomized parity fixtures in ``tests/fixtures/landis_r_parity/``. WS4 matches the R outputs
within ``1e-8`` for age mortality, ANPP, growth mortality, competition, and sumB. This is
kernel parity, not a spatial landscape run.

Heterogeneous reference
-----------------------

P211 extends the P200 case to four pixel groups with initial ages 10–100 and biomass 500–5000
g/m². The reference year-10 biomass is 10822; WS4 is 10809.75 (**-0.113%**). The script and
fixture are `scripts/landis_heterogeneous_reference.R` and
`tests/fixtures/landis_heterogeneous_reference/`.

Spatial reference
-----------------

P200 ran the full Biomass_core module on a 10 × 10, 100 m landscape for 10 years with a fixed
seed. The captured trajectory is in ``tests/fixtures/landis_spatial_reference/`` and the
reproducibility script is ``scripts/landis_spatial_reference.R``. This is a toy spatial
reference, not a regional LBSE reproduction.

WS4 spatial comparison
----------------------

P202 ran the WS4 LANDIS process on the P200 initial cohorts and found a -6.64% year-10 gap.
P210 aligned the annual transition with Biomass_core's age, `mAge`, floor, and integer-truncation
order. Year 1 is now 2694 vs 2694; year 10 is 9444 vs 9460 (**-0.169%**). The residual is
consistent with regeneration and module bookkeeping that the process does not yet implement.

Tests
-----

``tests/test_ecosystem_landis.py`` reproduces the published reference values for ANPP,
growth/mortality, competition, ``sumB``, and age mortality, including spin-up and
non-spin-up stages and the young-cohort regression case.

``LandisBatchSuccessionProcess`` applies the same kernels to the whole cohort table in one
landscape event per year. ``tests/test_ecosystem_dataset.py`` checks that the batch state and
volume match the per-fragment process exactly; only the event-log granularity differs.

The dataset runner maps compiled species codes to the reference traits with a provisional alias
table (``PL`` and ``PLI`` to jack pine, ``SX`` and ``SE`` to white spruce, ``BL`` to balsam fir,
``AT`` and ``ACT`` to trembling aspen, and so on). Unknown codes use the process default. The
aliases are a bridge, not a species-specific calibration; callers can supply exact
``LandisSpeciesTraits`` overrides.

A species cohort's ``biomass_t_ha`` is its density on its own area. The process converts it to
LANDIS ``B`` by multiplying by ``area_fraction`` so ``sumB`` is the whole-fragment biomass, then
converts the updated ``B`` back to density. This keeps multi-species competition and the
area-weighted fragment totals consistent.

Limits
------

- The process is a single-cohort-table transition, not a full landscape LBSE integration.
- Seed dispersal, serotiny, resprouting, and light competition beyond the kernel are not yet
  implemented.
- Reference values are numeric facts; no third-party implementation or prose is copied.
- No LBSE or LandR run; the comparison is kernel-level.
- Fuel fraction and snag decay remain provisional.
- The source modules are reference-only and mostly have no explicit licence file.
