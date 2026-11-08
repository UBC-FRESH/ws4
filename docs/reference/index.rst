=========
Reference
=========

The contracts, layer by layer: what a compiled dataset is, what the simulator guarantees, how the
optimizer prices a schedule, and the rules that make a schedule spatially real. These pages are the
authority on mechanism; the how-to guides are the authority on tasks, and the guides on symptoms.

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Page
     - What it specifies
   * - :doc:`compiled-dataset`
     - The runtime contract: the tables, the manifest, and the invariants that hold across them.
   * - :doc:`forestmodelxml`
     - The recipe format WS4 reads, the matrix it compiles, and the known gaps.
   * - :doc:`simulator`
     - The annual step, the schedule, and every file a run writes.
   * - :doc:`report-provenance`
     - The report sidecar: file digests, source metadata, run and dataset identifiers,
       and explicit uncertainty.
   * - :doc:`prices`
     - The read-only ``prices.v1`` scenario price-path table, its named paths, the
       base-relative comparison, and the ``not a forecast`` caveat.
   * - :doc:`optimizer`
     - Targets and the objective, the operator registry, the metaheuristics, and the MIP bound.
   * - :doc:`spatial`
     - Block topology, patch metrics and size classes, edge contrast, and the opening rules.
   * - :doc:`roads`
     - The network tables, least-cost routing, and the route accounts.
   * - :doc:`carbon`
     - The FEMIC package contract, SIT compile, libcbm runtime, optimizer ledger,
       fertilization, HWP lifecycle and system accounts, carbon yield curves, and the
       GCBM bridge boundary.
   * - :doc:`dhi`
     - Dynamic Habitat Index ingest, account semantics, provenance, and web layer.
   * - :doc:`structure-habitat`
     - The published Coops et al. structure index, required metrics, accounts, and gaps.
   * - :doc:`resilience`
     - Connectivity, age-class diversity, and fragmentation accounts from existing state.
   * - :doc:`species-composition`
     - Dominant-species ingest, block fractions, and VRI comparison.
   * - :doc:`recovery`
     - Post-fire spectral recovery ingest, block status, and caveats.
   * - :doc:`sdmd`
     - The stand density management contracts, the AU Explorer boundary, and the
       validation codes.
   * - :doc:`forest-condition`
     - The report-only forest-condition card schema, advisory alerts, and limits.
   * - :doc:`storyboard`
     - The one-page run storyboard that reuses the condition card.
   * - :doc:`performance`
     - The measured figures and how to reproduce them.
   * - :doc:`web`
     - The optional HTTP service over a run's artefacts, and the browser front end's contract.
   * - :doc:`femic-lidar`
     - Pinned FEMIC LidarBC bundles, checksums, and polygon support summaries.
   * - :doc:`disturbance`
     - Read-only ``femic.disturbance.v1`` events and the summary report.
   * - :doc:`event-log`
     - The unified event record, deterministic ordering, counter-based random tape, and
       replay contract.
   * - :doc:`ecosystem-package`
     - The optional state schema, cohort fractions, null bridge, and dataset join.
   * - :doc:`ecosystem-fire`
     - The first stochastic process: Poisson ignition, graph spread, mortality, salvage,
       and disturbance accounts.
   * - :doc:`ecosystem-scenarios`
     - Scenario ensembles, common random numbers, risk targets, and the out-of-sample report.
   * - :doc:`fire-behaviour`
     - The Rothermel surface-fire kernel, fuel and moisture contracts, standard cases, and
       derived intensity.
   * - :doc:`fire-weather`
     - The Canadian FWI moisture codes, the daily weather contract, and the reference
       validation.
   * - :doc:`fire-fbp`
     - The FBP fuel types, surface fuel consumption, surface rate of spread, and surface
       intensity.
   * - :doc:`fire-crown`
     - Crown fire initiation, the FBP crown fraction, the C6 crown rate of spread, and the
       active-crown threshold.
   * - :doc:`fire-growth`
     - The site grid, slope-adjusted effective wind, Huygens growth, and perimeter snapshots.
   * - :doc:`fire-scene`
     - The synthetic-tree scene, event-driven flame and smoke fields, and standalone viewer.
   * - :doc:`femic-hydrology`
     - Pinned FEMIC hydrology response bundles, checksums, flood-risk rows, and
       applicability metadata.

.. toctree::
   :maxdepth: 2
   :hidden:

   compiled-dataset
   forestmodelxml
   simulator
   report-provenance
   prices
   optimizer
   spatial
   roads
   carbon
   dhi
   structure-habitat
   resilience
   species-composition
   recovery
   forest-condition
   storyboard
   performance
   sdmd
   web
   femic-lidar
   disturbance
   event-log
   ecosystem-package
   ecosystem-fire
   ecosystem-scenarios
   fire-behaviour
   fire-weather
   fire-fbp
   fire-crown
   fire-growth
   fire-scene
   femic-hydrology
