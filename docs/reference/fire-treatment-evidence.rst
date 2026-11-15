Fire-treatment evidence
=======================

Purpose
-------

This page records published fuel-treatment effect ranges and the comparison gate WS4 will use
once it can simulate a treatment prescription.

WS4 currently has no thinning, prescribed-fire, or fuel-load treatment pathway. It has
containment/firebreak masks and a small VRI treatment-label mapping. A containment simulation
must not be reported as validation of the fuel-treatment ranges below.

Published evidence
------------------

.. list-table::
   :header-rows: 1

   * - Treatment
     - Mean severity reduction
     - Source
   * - Thinning + prescribed fire
     - 62–72%
     - Davis et al. 2024
   * - Prescribed fire only
     - 62%
     - Davis et al. 2024
   * - Thinning + pile burning
     - 62%
     - Davis et al. 2024
   * - Thinning only
     - 27%
     - Davis et al. 2024
   * - Treatment older than 10 years
     - 28%
     - Davis et al. 2024

Source: Davis et al. (2024), *Forest Ecology and Management* 561:121885,
https://doi.org/10.1016/j.foreco.2024.121885. The values are western-US conifer meta-analysis
means, not a BC-specific transfer value.

Available mechanism
--------------------

``ws4.fire.treatment.apply_fuel_treatment`` converts a declared mask of burnable cells to an
explicit FBP fuel type. It requires the caller to name the replacement and refuses to modify
non-fuel cells. It does not choose a prescription, fuel type, or treatment extent.

Comparison gate
----------------

``ws4.fire.treatment.classify_effect`` computes the fractional reduction from a supplied
untreated and treated metric. It reports whether the result is below, within, or above the
published interval.

Decision
--------

**No-go for treatment-effect validation now.** The evidence registry is usable, but a WS4
simulation cannot be scored against it until a treatment prescription changes fuel and canopy
structure in the fire model.

A generic fuel-conversion mechanism now exists, but the prescription mapping is still missing:
which FBP fuel type represents thinning, prescribed fire, or surface-fuel reduction is an
expert decision, not a default. Until that mapping is supplied, report containment/firebreak
effects separately.
