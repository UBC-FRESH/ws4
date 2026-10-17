Optimizer
=========

The optimizer searches for a schedule that meets a set of goal-programming targets over a compiled
dataset. It is a layered, pluggable stack (``notes/adr/0007``): an objective, a problem adapter, a
registry of neighbourhood operators, and a metaheuristic solver. Every search records its seed, so a
result is reproducible.

Objective
---------

A target names one account and the first year of a period, with a ``minimum``, a ``maximum``, or
both. **The simulation step is one year and is not configurable.** Treatments, growth, transitions and
road events are all simulated annually; the **account** time step is a whole number of years — the
period length — and is what ``period_width`` sets (default 1). Five and ten years are the convention
in forest planning; any whole multiple of a year is accepted. For an additive account (volume, area,
a count) the account value for the period is the sum of its years, compared to the levels, so a decade
target is ``period_width: 10``; the penalty is the weighted shortfall below the minimum plus the
weighted excess above the maximum, and the objective is the total penalty (lower is better). A **patch**
account is a snapshot of the map rather than an additive quantity, so a patch target is read at the
first year of its period. Targets load from a YAML file:

.. code-block:: yaml

   targets:
     - account: feature.Volume
       year: 0
       maximum: 500
     - account: product.Yield.managed.Conif
       year: 0
       minimum: 800000
       maximum: 800000
       period_width: 10
     - account: patch.harvest.10_50.size
       year: 0
       minimum: 100
       min_weight: 10000
       shape: non_linear

**Period numbering** follows the established convention: **period 0 is a zero-length period describing
the instantaneous state of the forest before the simulation starts**, and periods **1 to N** are the
accounting periods the targets are set on. A target's ``year`` is a year, not a period index: a target
at ``year: 0`` with ``period_width: 10`` is the level for period 1, which covers years 0 to 9.

**Flow targets** express even flow or non-declining yield without pinning the level, which is the
established way to state them: the flow target is set to zero with a weight, and a separate target on
the same account sets the level.

.. code-block:: yaml

   targets:
     # the level
     - account: product.Yield.managed.Conif
       year: 0
       minimum: 900000
       maximum: 1400000
       period_width: 10
     # even flow: the sum of each period's distance from the mean must be zero
     - account: product.Yield.managed.Conif
       year: 0
       flow: even
       period_width: 10
       minimum: 0
       maximum: 0
       min_weight: 0.001
       max_weight: 0.001
     # non-declining yield over the final periods
     - account: product.Yield.managed.Conif
       year: 0
       flow: ndy
       period_width: 10
       flow_start: 150
       flow_end: 200
       minimum: 0
       maximum: 0
       min_weight: 1.0

``flow.even`` sums ``|period - mean|`` over its window and ``flow.ndy`` sums how much each period falls
below the one before it; ``flow_start`` and ``flow_end`` (in years) clip the window, defaulting to the
whole horizon. Both aggregate whole periods, so they are period-level terms rather than per-year cells.

The weights file is accepted by the command line and the configuration. The spatial constraints add a
weighted penalty to the objective (see :doc:`spatial`): a maximum opening size, a green-up interval,
and a core-area rule. Edge contrast accounts (``--edge-elements``) are added to the account values, so
they can be targeted. The penalties are disabled only by the explicit ``--spatial-override``.

Search stack
------------

The problem adapter (``ws4.opt.core.Problem``) carries the objective evaluator, the candidate moves
per block, and the operator registry. The operators are:

- ``toggle`` — assign a treatment to a block, or clear an assigned block;
- ``shift`` — move an assigned block to a different year for the same treatment;
- ``swap`` — exchange the assignments of two blocks;
- ``lns`` — large-neighbourhood search: destroy a fraction of the schedule and repair it.

The solvers are simulated annealing (``sa``), tabu search (``tabu``), and iterated local search
(``ils``), selected by ``OptimizeConfig.metaheuristic``. A run may use multiple starts
(``OptimizeConfig.starts``), serial or across a process pool (``OptimizeConfig.workers``), keeping the
best. ``OptimizeConfig.warm_start`` seeds the search from each block's first candidate.

Simulated annealing cools geometrically by default (``OptimizeConfig.temperature`` and
``OptimizeConfig.cooling``). Setting ``OptimizeConfig.cooling_mode`` to ``adaptive`` (``--cooling-mode
adaptive``) uses the polynomial-time schedule of Aarts and Van Laarhoven instead: the initial
temperature is set from the observed uphill moves and decreased from the objective spread, so the
schedule needs no per-instance tuning. ``OptimizeConfig.cooling_window`` (``--cooling-window``) sets
the iterations per temperature; ``geometric`` remains the default.

For scale, an **island model** (``OptimizeConfig.islands`` and ``episodes``, or ``--islands`` /
``--episodes``) runs several islands in parallel as processes and, after each episode, migrates the
global best schedule into every island as the next episode's starting point. The result is
deterministic for a given seed.

The mixed-integer layer (``ws4.opt.mip``) solves an option-selection MILP (HiGHS via
``scipy.optimize.milp``) for a penalty **lower bound** and a candidate schedule. Enabling
``OptimizeConfig.mip_bound`` (``--mip-bound``) records the bound, the gap, and the bound status in the
summary. With ``--topology`` and ``--max-opening-ha`` the bound also enforces the stand-centred
opening constraints, which tighten it as the cap falls.

Run
---

.. code-block:: bash

   ws4 optimize --dataset build/compiled --targets targets.yaml --weights weights.yaml \
                --threads 8 --seed 42 --out opt

When a route configuration is given (``OptimizeConfig.route_config_path`` or
``--route-config``), the objective is evaluated with the route model, and the route accounts and
duplicate accounts (see :doc:`roads`) are resolved into the account values, so targets can be set on
accounts such as ``route.Total.haul``.

Watch
-----

``ws4 watch`` runs the same search and paints the realized-versus-target window of an account in
place: one column per period, the minimum/maximum target band shaded, and the realized value drawn
over it, coloured by status (green inside the window, red below the minimum, blue above the
maximum). Targets are per year; the view sums them into periods of ``--period-width`` years, so
per-year levels that sum to a periodic target read as the periodic window. ``--plain`` prints one
final frame instead of a live view. The live view repaints on a fixed heartbeat
(``--refresh`` seconds, default 2), independent of the search, so the header (iteration rate,
objective) stays current even between improvements.

Repeat ``--account`` to watch several accounts **side by side, one window each** — each with its own
axis, title and penalty, so accounts with different units read correctly. A **percentage** account
(the patch size-class ``…<class>.size`` shares of total patch area) is averaged over a period, not
summed, since summing a share would multiply it by the period length. That is how to see a volume
target (m3 per period) and a patch size-class target (percent of patch area) converging together:

.. code-block:: bash

   ws4 watch --dataset build/compiled --targets targets.yaml \
             --account product.Yield.managed.Conif --account patch.harvest.10_50.size \
             --period-width 10 --years 200 --iterations 5000 --warm-start \
             --patch-accounts patches.yaml --topology topology.csv

Patch size distribution
-----------------------

Patch accounts (the size distribution of connected patches of a criteria feature — see
:doc:`spatial`) are **non-additive**: a patch spans adjacent blocks, so the move-based delta does not
apply directly. Give ``--patch-accounts`` (a YAML of definitions) with ``--topology``, and set targets
on the sub-accounts:

.. code-block:: yaml

   accounts:
     - name: patch.harvest
       criteria: feature.Seral.young
       threshold: 0.5
       size_classes: [5.0, 10.0, 50.0, 250.0, .inf]
       search_distance: 200.0

Targets then read ``patch.harvest.50_150.area``, ``…size``, ``…frequency``, or ``…shape``.

``search_distance`` (metres) is how far apart two blocks may be and still be neighbours. It
defaults to ``0``, which joins only blocks that literally touch (their polygons share a vertex);
a larger value admits more neighbour edges, so patches can only get **larger**. The topology's
``DISTANCE`` column is the shortest distance between the two blocks' polygons, so a non-zero
value is a real gap — a road, a creek, a right-of-way — that the default keeps out of a patch.

The ``criteria`` feature decides what a patch *is*. ``feature.Seral.regen`` is a recently
disturbed stand (up to ~37 years), which is what a harvest opening looks like;
``feature.Seral.young`` is a seral stage 42-97 years after disturbance, so a patch of it is a
band of young forest, not an opening. Pick the criterion that matches the question.

Each block's criterion series is cached per chain, the adjacency is indexed by block, and a move
updates only the components near the moved block — a resize, a merge, a new standalone patch, or a
removal/split — so a patch evaluation costs tens of milliseconds rather than a full re-simulation.

Calibrate
---------

Targets of different magnitudes unbalance the objective: the largest term dominates and the search
freezes before the others are considered. ``ws4 calibrate`` runs a short pilot search, records the
largest penalty each target reaches, and writes a targets file whose weights are rescaled so the
peaks match. Pass the result to ``optimize`` or ``watch``.

.. code-block:: bash

   ws4 calibrate --dataset build/compiled --targets targets.yaml --out calibrated.yaml \
                 --topology topology.csv --patch-accounts patches.yaml --warm-start
   ws4 optimize --dataset build/compiled --targets calibrated.yaml --out opt

A target that never fires in the pilot keeps its own weights. Match ``--warm-start`` to the run's
setting: a warm-started pilot starts from the same schedule, so terms that only appear once blocks
are harvested (such as a patch term) register.

Outputs
-------

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - File
     - Contents
   * - ``schedule.csv``
     - The incumbent schedule (``block_id,treatment,period``).
   * - ``summary.json``
     - The run summary: objective, iterations, seed, metaheuristic, operators, block count, status,
       and the dataset manifest.
   * - ``account_values.csv``, ``product_values.csv``
     - The simulated account and product values for the incumbent schedule.
   * - ``report_accounts.csv``, ``report_targets.csv``
     - The account summary and the per-target status.
   * - ``telemetry.jsonl``
     - A run header and one record per search step.

API
---

.. autoclass:: ws4.opt.engine.OptimizeConfig
   :members:

.. autoclass:: ws4.opt.engine.Optimizer
   :members:

.. autoclass:: ws4.opt.cooling.AdaptiveCooling
   :members:

.. autoclass:: ws4.opt.cooling.TemperatureSchedule
   :members:

.. autoclass:: ws4.opt.core.Problem
   :members:

.. autofunction:: ws4.opt.objective.load_targets

.. autofunction:: ws4.opt.objective.objective

.. autofunction:: ws4.opt.objective.penalty

.. autofunction:: ws4.opt.objective.objective_terms

.. autofunction:: ws4.opt.objective.balance_targets

.. autofunction:: ws4.opt.calibrate.pilot_peaks

.. autofunction:: ws4.opt.calibrate.calibrate

.. autofunction:: ws4.opt.calibrate.write_targets

.. autofunction:: ws4.opt.watch.run_watch

.. autoclass:: ws4.opt.watch.TargetWindow
   :members:

.. autofunction:: ws4.opt.mip.bound_for

.. autoclass:: ws4.opt.telemetry.RunLogger
   :members:

.. autofunction:: ws4.opt.telemetry.read_records
