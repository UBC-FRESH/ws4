=======================
How WS4 is put together
=======================

This page is the map: what the layers are, how data moves between them, and which consequences of
the design catch people out. It assumes you have run :doc:`quickstart`.

The layers
----------

.. list-table::
   :header-rows: 1
   :widths: 22 34 44

   * - Layer
     - Modules
     - Responsibility
   * - Ingestion
     - ``ws4.io``, ``ws4.build``
     - Read a model recipe and a fragment inventory, expand the strata, and compile the matrix
       into a dataset. ``ws4.build.legacy`` imports an existing matrix instead.
   * - The contract
     - ``ws4.model.schema``, ``ws4.model.api``
     - The compiled dataset: one Parquet table per matrix table plus a manifest that records the
       schema version, the options, and the inputs' digests. Everything downstream reads only this.
   * - Simulation
     - ``ws4.sim``
     - Step the forest one year at a time, apply treatments, and report account values. Growth and
       yield come from a precomputed age grid, so a curve is a gather.
   * - Space
     - ``ws4.patch``
     - Block topology, patch metrics and size classes, edge contrast, and the opening, green-up,
       and core-area rules.
   * - Roads
     - ``ws4.roads``
     - The road network, least-cost routing to destinations, and the haul, build, and maintenance
       accounts.
   * - Optimization
     - ``ws4.opt``
     - The objective and its targets, the neighbourhood operators, the solvers, the incremental
       evaluator, the patch model, the MIP bound, the watcher, and the run engine.
   * - Interfaces
     - ``ws4.cli``, ``ws4.report``
     - The command line, the run outputs, and the account and target reports.

Data flow
---------

.. mermaid::

   flowchart LR
     A[recipe + fragments] -->|ws4 build| B[(compiled dataset)]
     B --> C[simulator]
     C --> D[account values]
     D --> E[objective and targets]
     F[topology] --> G[patch model]
     H[road tables] --> I[route model]
     G --> E
     I --> E
     E -->|operators + solver| J[schedule]
     J -->|feedback| E
     J --> K[run directory]
     K --> L[summary, account and target reports]

The loop on the right is the search: a **move** changes a block's treatment chain, the objective's
delta is priced exactly without re-simulating, and the solver accepts or rejects it. The patch and
route models participate in their own way — see "the pitfalls" below.

Carbon is a sidecar to this flow rather than a dataset column: a FEMIC package plus a schedule
compiles SIT tables, libcbm supplies ecosystem pools and fluxes, and an optional HWP ledger turns
merchantable inflow into product, end-of-life, and displacement accounts. See
:doc:`../reference/carbon`.

The design principles
---------------------

**Fragments compile; blocks aggregate.** The compiled matrix is fragment-level and small; blocks are
a runtime view used for operability, reporting, and spatial metrics. One matrix therefore serves
many block layouts.

**The compiled dataset is the contract.** Ingestion is the only producer, execution is the only
consumer, and the boundary is a directory of Parquet tables with a manifest. If a study is
reproducible, it is because this artefact is.

**Space is part of the model, not post-processing.** Adjacency, patch structure, and access
constraints are inside simulation and optimization, so a schedule that cannot be cut in the real
world is not a schedule the search will produce.

**The simulation steps by offset; the accounting is by period.** Treatments happen at a simulation
offset (offset 0 is the first year); a target reads the account over a whole number of offsets
(``period_width``, usually 5 or 10). Period ``p >= 1`` covers offsets ``(p - 1) * period_width``
through ``p * period_width - 1``, so ``period: 1, period_width: 10`` covers offsets 0 to 9 and displays
as the decade ending in year 10. The year is a display label only (``year = offset + 1``). Period 0 is
the zero-length pre-simulation snapshot at offset -1; the periods targets use are numbered from 1.

**Reproducibility is a feature.** Every search records its seed, and the simulator is deterministic
given a schedule.

The pitfalls
------------

These all follow from the design, and each has a fix:

* **An indifferent search.** The objective prices only what the targets read, so an unconstrained
  year costs nothing and the search will choose it arbitrarily. Say what you care about — a later
  year's floor, a flow target, or a patch target. See :doc:`first-model`.
* **A flow term that is infinite until primed.** Even-flow and non-declining targets divide by a
  balance. While a balance is zero the term is infinite, which is definitional rather than a bug: run
  once with a linear volume floor so every period carries wood, then switch the flow target on. See
  :doc:`../howto/even-flow`.
* **Patch targets are not additive.** A patch spans blocks, so a move is priced through the patch
  model and patch statistics are kept only at the years a target reads. That is why a patch run
  costs more per iteration than a volume run. See :doc:`../howto/patch-targets`.
* **Some accounts turn off the fast path.** A move is priced as a delta when the accounts are
  additive, which covers volume, area, the patch model, and the haul, maintenance, and volume route
  accounts. Edge contrast, a route **build** account, and duplicate accounts are not additive, so a
  run that uses any of them does a whole-schedule pass per evaluation and takes much longer per
  iteration. Keep them out while you tune the rest. See :doc:`../reference/performance`.
* **A dataset that no longer matches its manifest.** Compiled datasets are validated on the way in
  (``ws4 validate``) and are not meant to be edited by hand; if you need different tables, recompile.

.. note::

   If you develop against this codebase, read ``AGENTS.md`` at the repository root: it is the working
   contract for humans and coding agents, and it names the notes and ADRs behind each decision above.

Next
----

* :doc:`../howto/index` — the task guides.
* :doc:`../reference/index` — the contracts, layer by layer.
