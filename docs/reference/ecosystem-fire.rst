Fire process
============

Purpose
-------

Fire is the first stochastic landscape process in the ecosystem layer. It consumes the
event record, the counter-based tape, and the cohort state, and it is the vertical slice that
proves the architecture end to end. It is a LANDIS-class skeleton, not a calibrated
fire-behaviour model: ignition is Poisson, spread is graph percolation, severity drives
cohort mortality, and salvage is a deterministic controlled source.

The process is annual. It does not modify the compiled management dataset; it reads the
cohort state and writes a replayable event log, disturbance rows, and account values.

Ignition
--------

Every eligible fragment-year draws a Poisson count:

.. code-block:: text

   count = Poisson(ignition_rate_per_fragment_year)
   key   = (scenario seed, "fire", fragment, year, 0)

A fragment is eligible when its area-weighted fuel is positive. Each ignition in the count
receives a uniform time inside the year and an ignition event with phase ``ignition``. The
count is the analytic oracle: over many fragment-years the total must approach the configured
rate.

Spread
------

An ignition starts a breadth-first walk over the undirected landscape graph. For each edge
into an unburned target fragment, the crossing probability is:

.. code-block:: text

   p = base_spread_probability
       × min(1, target fuel / fuel_reference_t_ha)
       × exp(-distance_m / distance_scale_m)
       × wind factor

The wind factor is one when wind is disabled or the edge has no bearing. Otherwise it is
``max(0, 1 + wind_strength × cos(bearing - wind_direction))``. The target fragment's fuel is
used, so a zero-fuel barrier stops the fire. The draw is keyed by the edge, so the same
scenario tape gives the same crossing decision regardless of traversal order.

Every burned fragment produces one ``fire`` event with phase ``propagation``, a severity
class and value, the mortality fraction, the fragment area, and the event that caused it.
The event id is derived from the ignition event id and the fragment id, so two fires in one
year cannot collide.

Severity and mortality
----------------------

Severity is a uniform draw in ``[severity_min, severity_max]``, keyed by the fragment and
year. Mortality is:

.. code-block:: text

   mortality = min(1, severity × mortality_factor)

For every cohort in the burned fragment, the killed area fraction becomes a new age-zero
cohort with zero live biomass and zero fuel. The killed biomass leaves a snag pool of
``biomass_t_ha × snag_fraction``. The surviving cohort keeps the remaining fraction. The
total area fraction stays one, so the area-conservation check passes after every fire.

Salvage
-------

The salvage source is deterministic. After ``salvage_delay_years`` it emits one ``salvage``
event per burned fragment with a positive snag volume. The event is a controlled event with
phase ``treatment``, a parent link to the fire event, and the merchantable volume:

.. code-block:: text

   volume_m3 = Σ snag_t_ha × area_fraction × fragment_area_ha × volume_per_t

Applying the event removes the fragment's snags. The event log keeps the volume, so the
account is auditable even after the state changes.

Accounts
--------

A run writes account rows with ``year``, ``account``, and ``value``:

- ``fire.count``
- ``fire.burned_area_ha``
- ``fire.mortality_area_ha``
- ``fire.severity_area_weighted``
- ``fire.killed_biomass_t``
- ``fire.snag_created_t``
- ``fire.emitted_biomass_t``
- ``salvage.count``
- ``salvage.area_ha``
- ``salvage.volume_m3``
- ``state.biomass_t``
- ``state.fuel_t``
- ``state.snag_t``

The biomass accounts close a live-mass balance: the initial live biomass equals the final live
biomass plus cumulative killed biomass, and killed biomass equals the snag-created and emitted
shares. That is a biomass-mass check, not a full CBM pool-and-flux accounting; the carbon
ledger's fire/salvage event source is a later task.

The result also writes ``events.json`` (the event log), ``disturbances.json`` (the fire
events as ``femic.disturbance.v1`` consumer rows), ``cohorts.csv``, and ``summary.json``.
The disturbance export maps simulation offsets to calendar years with ``start_year`` (default
1900), because the disturbance contract's ``year`` is a calendar year while the event log's
``year`` is the annual accounting offset.

Configuration
-------------

``FireConfig`` fields:

.. list-table::
   :header-rows: 1
   :widths: 38 18 44

   * - Field
     - Default
     - Meaning
   * - ``ignition_rate_per_fragment_year``
     - 0.01
     - Poisson ignition rate per eligible fragment-year.
   * - ``base_spread_probability``
     - 0.45
     - Base edge-crossing probability.
   * - ``fuel_reference_t_ha``
     - 20.0
     - Target fuel at which the fuel factor reaches one.
   * - ``distance_scale_m``
     - 250.0
     - Exponential distance decay scale.
   * - ``wind_direction_deg``
     - null
     - Wind direction clockwise from north; null disables wind.
   * - ``wind_strength``
     - 0.0
     - Wind strength in [0, 1].
   * - ``severity_min``
     - 0.2
     - Minimum severity draw.
   * - ``severity_max``
     - 1.0
     - Maximum severity draw.
   * - ``mortality_factor``
     - 0.8
     - Fraction of severity that kills a cohort.
   * - ``snag_fraction``
     - 0.1
     - Fraction of killed biomass left as snags.
   * - ``salvage_delay_years``
     - 1
     - Delay before a burned fragment is salvaged.
   * - ``salvage_volume_m3_per_t``
     - 1.0
     - Merchantable volume per tonne of snag.
   * - ``max_spread_steps``
     - 10000
     - Guard against a runaway fire.

Example
-------

The repository ships a synthetic grid demo:

.. code-block:: bash

   python examples/ecosystem_fire_demo.py

The same run is available programmatically:

.. code-block:: python

   from ws4.ecosystem import run_fire_demo

   result = run_fire_demo(rows=5, cols=5, years=30, seed=7)
   print(result.log.replay_token)
   print(result.accounts.tail())

A run over a compiled dataset and an ecosystem package:

.. code-block:: python

   from ws4.ecosystem import FireConfig, FireRun, load_ecosystem_package, synthetic_grid

   package = load_ecosystem_package("dataset/ecosystem")
   state = package.cohort_state("dataset")
   _, _, edges = synthetic_grid(5, 5)
   result = FireRun(
       state,
       edges,
       FireConfig(ignition_rate_per_fragment_year=0.02),
       scenario_id="base",
       seed=42,
       package_hashes=(("ecosystem", package.fingerprint),),
   ).run(30)
   result.write("runs/base-fire")

Oracles
-------

- **Poisson count.** A single fragment over 1,000 years at rate 0.05 lands near 50 ignitions.
- **Geometric chain.** A one-dimensional chain with base probability 0.5 has a mean burn
  length of ``1 / (1 - 0.5) = 2`` fragments from one ignition.
- **Barrier.** A zero-fuel column stops a fire that would otherwise cross the grid.
- **Wind.** A downwind edge crosses at probability one while its upwind reverse does not.
- **Area conservation.** Fire and salvage preserve each fragment's area fractions.
- **Replay.** The same state, configuration, and seed produce the same event log and digest.

Limits
------

- The process is not calibrated to fire behaviour, fuels, weather, or topography.
- Time is annual. Continuous-time event scheduling is a later task.
- Fires in the same year are processed in ignition order; overlapping fires are not treated
  as a simultaneous front.
- Other processes (wind, insects, drought, succession) are not implemented yet.
- The optimizer does not yet search fire-aware policies. Scenario ensembles and risk targets
  are P144.5.

Cross-references
----------------

- :doc:`ecosystem-package`
- :doc:`ecosystem-scenarios`
- :doc:`event-log`
- :doc:`compiled-dataset`
- :doc:`disturbance`
