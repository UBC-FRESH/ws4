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

Tests
-----

``tests/test_ecosystem_landis.py`` reproduces the published reference values for ANPP,
growth/mortality, competition, and ``sumB``, including spin-up and non-spin-up stages and the
young-cohort regression case.

Limits
------

- The kernel is not yet wired into the P180 succession process.
- Reference values are numeric facts; no third-party implementation or prose is copied.
- The source modules are reference-only and mostly have no explicit licence file.
