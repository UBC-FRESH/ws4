Optimizer
=========

The optimizer searches for a schedule that meets a set of goal-programming targets over a compiled
dataset. It is a layered, pluggable stack (``notes/adr/0007``): an objective, a problem adapter, a
registry of neighbourhood operators, and a metaheuristic solver. Every search records its seed, so a
result is reproducible.

Objective
---------

A target names one account and the first year of a period, with a ``minimum``, a ``maximum``, or
both. Treatments are scheduled by year; the **accounting is per period** — with ``period_width``
(default 1) the account is summed over the period's years and compared to the levels, so a decade
target is ``period_width: 10``. The penalty is the weighted shortfall below the minimum plus the
weighted excess above the maximum; the objective is the total penalty (lower is better). Targets load
from a YAML file:

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

For scale, an **island model** (``OptimizeConfig.islands`` and ``episodes``, or ``--islands`` /
``--episodes``) runs several islands in parallel as processes and, after each episode, migrates the
global best schedule into every island as the next episode's starting point. The result is
deterministic for a given seed.

The mixed-integer layer (``ws4.opt.mip``) solves an option-selection MILP (HiGHS via
``scipy.optimize.milp``) for a penalty **lower bound** and a candidate schedule. Enabling
``OptimizeConfig.mip_bound`` records the bound and the gap in the summary.

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

.. code-block:: bash

   ws4 watch --dataset build/compiled --targets targets.yaml \
             --account product.Yield.managed.Conif --period-width 10 --years 50 \
             --iterations 5000 --warm-start

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
``search_distance`` (metres) is the neighbourhood: only topology edges no longer than it join
blocks, so a patch stays within it. Each block's criterion series is cached per chain, the
adjacency is indexed by block, and a move updates only the components near the moved block —
a resize, a merge, a new standalone patch, or a removal/split — so a patch evaluation costs
tens of milliseconds rather than a full re-simulation.

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

.. autoclass:: ws4.opt.core.Problem
   :members:

.. autofunction:: ws4.opt.objective.load_targets

.. autofunction:: ws4.opt.objective.objective

.. autofunction:: ws4.opt.objective.penalty

.. autofunction:: ws4.opt.watch.run_watch

.. autoclass:: ws4.opt.watch.TargetWindow
   :members:

.. autofunction:: ws4.opt.mip.bound_for

.. autoclass:: ws4.opt.telemetry.RunLogger
   :members:

.. autofunction:: ws4.opt.telemetry.read_records
