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
An optional species ``age_volume_curves`` mapping overrides the biomass rate with age-based
volume per hectare. Intermediate ages interpolate; ages outside the range clamp to the endpoint.
``age_volume_curves_from_frame`` loads these curves from a compiled ``curves.parquet`` table.

The bridge can attach ``volume_m3_ha`` and ``volume_m3`` to a management frame keyed by
``fragment_id``.

Limits
------

- The parameters are provisional and are not calibrated to observed stands.
- Regeneration is a single-cohort establishment rule, not species competition.
- The bridge does not modify the compiled dataset or its yield curves.
- The executor remains annual; continuous-time ecology is later work.


Offset convention
-----------------

An estate ``simulate(..., years=N)`` writes offsets 0 to N-1 and ages cohorts to ``N-1`` annual
steps. The process executor's ``horizon_years`` counts transitions. For a five-year estate run,
four process transitions match the final offset; five transitions are one annual step ahead.


Track change
------------

Cohorts carry an optional ``track_id``. The treatment source records the compiled
``(source_track, treatment)`` to target-track transition, and new cohorts take the target track.
The volume bridge prefers that track's compiled age curve and falls back to the species curve when
the cohort has no track curve. A five-year CC comparison now matches the estate at 390 m3: the
harvested block contributes the managed age-2 volume instead of staying on the natural curve.

Within a year, treatments run before growth. This matches the estate's treatment-then-age order
and lets a cohort created by a treatment reach the same age as the estate's final offset. The
process horizon still uses the offset convention above: four process transitions match a five-year
estate run.
