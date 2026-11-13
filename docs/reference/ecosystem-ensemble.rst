Process scenario ensembles
==========================

Purpose
-------

``ws4.ecosystem.ensemble`` runs the actual process engine outside the optimizer:
fire, succession, salvage, regeneration, and the provisional volume bridge, one executor per
scenario seed. It produces per-year, account-like metrics and optionally risk-aggregates them
with the existing scenario layer.

This is a process-driven ensemble, not the P181 account-overlay optimizer path.

Metrics
-------

Each year records:

- ``fire.count``, ``fire.burned_area_ha``, ``fire.mortality_area_ha``;
- ``succession.count``, ``salvage.count``, ``regeneration.count``;
- ``state.biomass_t``, ``state.fuel_t``, ``state.snag_t``;
- ``bridge.volume_m3``.

Usage
-----

.. code-block:: python

   from ws4.ecosystem import (
       ProcessEnsembleConfig,
       run_process_ensemble,
       ScenarioSet,
   )

   result = run_process_ensemble(
       state,
       edges,
       ProcessEnsembleConfig(horizon_years=20, fire=fire_config),
       scenarios,
       targets,
   )
   result.write("runtime/process-ensemble")

Artifacts are ``process_values.csv``, ``process_aggregated.csv``, and
``process_summary.json``.

Limits
------

- The process state is standalone; there is no management-schedule bridge yet.
- A harvest schedule does not change fuel before the process runs.
- The volume bridge remains provisional.
- The optimizer uses the P181 account overlay in its inner loop; P183 is an outside-loop
  process ensemble.
