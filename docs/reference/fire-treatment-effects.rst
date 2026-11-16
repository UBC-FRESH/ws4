Open FFS treatment effects
==========================

Purpose
-------

``ws4.fire.treatment_effects`` pairs pre- and post-treatment measurements from the public
National Fire and Fire Surrogate study and summarizes changes in canopy cover, live basal area,
and surface fuel.

Source
------

USDA Forest Service Research Data Archive ``RDS-2016-0009``. This is open public data from US
FFS sites, not a BC treatment inventory.

Results
-------

Median percent change by treatment:

.. list-table::
   :header-rows: 1

   * - Treatment
     - Canopy cover
     - Live basal area
     - Surface fuel
   * - burn-only
     - −3.1%
     - −0.8%
     - −45.2%
   * - thin-only
     - −10.8%
     - −28.5%
     - +50.6%
   * - thin-burn
     - −22.9%
     - −29.0%
     - −3.5%
   * - control
     - +6.4%
     - +0.8%
     - −8.3%

The tradeoff is explicit: thinning alone increases surface fuel, while burning reduces it.
Thin-burn reduces both canopy structure and surface fuel.

Limits
------

- US FFS sites, not BC.
- The mapping from measured changes to FBP fuel/canopy inputs is a separate modelling choice.
- BC Wildfire CRI Fuel Treatments are marked Access Only and are not used.
- No operational claim.

Report: ``notes/reports/ffs-treatment-effects.md``.
