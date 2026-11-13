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

Process
-------

``LandisSuccessionProcess`` runs in the ``growth`` phase and applies the kernel to each
fragment. ``LandisSuccessionConfig`` supplies per-species traits and a default. The process
can replace the default logistic succession source through
``ProcessEnsembleConfig.succession_process``.

Tests
-----

``tests/test_ecosystem_landis.py`` reproduces the published reference values for ANPP,
growth/mortality, competition, and ``sumB``, including spin-up and non-spin-up stages and the
young-cohort regression case.

Limits
------

- The process is a single-cohort-table transition, not a full landscape LBSE integration.
- Seed dispersal, serotiny, resprouting, and light competition beyond the kernel are not yet
  implemented.
- Reference values are numeric facts; no third-party implementation or prose is copied.
- The source modules are reference-only and mostly have no explicit licence file.
