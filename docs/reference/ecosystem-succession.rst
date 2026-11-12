Succession, regeneration, and the yield bridge
==============================================

Purpose
-------

P180 adds the first living ecological processes to the generic executor:

- deterministic succession over the cohort state;
- stochastic juvenile establishment after disturbance;
- a provisional species-biomass-to-volume bridge.

The processes are annual and fragment-level. The compiled management dataset remains the
authority; the bridge is an ecological view, not a replacement for the yield curves.

Succession
----------

``SuccessionProcess`` runs in the ``growth`` phase. It increments cohort age, grows live
biomass toward a species maximum, accumulates fuel as a fraction of biomass, and decays snags.
``SpeciesGrowth`` and ``SuccessionConfig`` carry the parameters; the defaults are provisional.

Regeneration
------------

``RegenerationProcess`` runs in the ``regeneration`` phase. It finds juvenile cohorts and
draws establishment from the scenario random tape. Establishment raises juvenile biomass and
fuel to declared minimums without changing area fractions. The draw is keyed by process,
fragment, and year, so replay and common random numbers hold.

Yield bridge
------------

``SpeciesVolumeBridge`` maps cohort biomass to merchantable volume:

.. code-block:: text

   volume_m3 = biomass_t_ha × area_fraction × fragment_area_ha
               × volume_m3_per_t[species] × merchantable_fraction

``VolumeBridgeConfig`` records species rates, the default rate, the merchantable fraction,
the schema version, and the calibration status/source. The default status is ``provisional``.
The bridge can attach ``volume_m3_ha`` and ``volume_m3`` to a management frame keyed by
``fragment_id``.

Limits
------

- The parameters are provisional and are not calibrated to observed stands.
- Regeneration is a single-cohort establishment rule, not species competition.
- The bridge does not modify the compiled dataset or its yield curves.
- The executor remains annual; continuous-time ecology is later work.
