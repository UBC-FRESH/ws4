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
   * - :doc:`optimizer`
     - Targets and the objective, the operator registry, the metaheuristics, and the MIP bound.
   * - :doc:`spatial`
     - Block topology, patch metrics and size classes, edge contrast, and the opening rules.
   * - :doc:`roads`
     - The network tables, least-cost routing, and the route accounts.
   * - :doc:`carbon`
     - The FEMIC carbon package contract, its tables, and the track-name join.
   * - :doc:`dhi`
     - Dynamic Habitat Index ingest, account semantics, provenance, and web layer.
   * - :doc:`structure-habitat`
     - The published Coops et al. structure index, required metrics, accounts, and gaps.
   * - :doc:`resilience`
     - Connectivity, age-class diversity, and fragmentation accounts from existing state.
   * - :doc:`performance`
     - The measured figures and how to reproduce them.
   * - :doc:`web`
     - The optional HTTP service over a run's artefacts, and the browser front end's contract.
   * - :doc:`femic-lidar`
     - Pinned FEMIC LidarBC bundles, checksums, and polygon support summaries.
   * - :doc:`disturbance`
     - Read-only ``femic.disturbance.v1`` events and the summary report.
   * - :doc:`femic-hydrology`
     - Pinned FEMIC hydrology response bundles, checksums, flood-risk rows, and
       applicability metadata.

.. toctree::
   :maxdepth: 2
   :hidden:

   compiled-dataset
   forestmodelxml
   simulator
   optimizer
   spatial
   roads
   carbon
   dhi
   structure-habitat
   resilience
   performance
   web
   femic-lidar
   disturbance
   femic-hydrology
