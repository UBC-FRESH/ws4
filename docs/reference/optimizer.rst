Optimizer
=========

The optimizer searches for a schedule that meets a set of goal-programming targets over a compiled
dataset. It is a layered, pluggable stack (``notes/adr/0007``): an objective, a problem adapter, a
registry of neighbourhood operators, and a metaheuristic solver. Every search records its seed, so a
result is reproducible.

Objective
---------

A target names one account and one year, with a ``minimum``, a ``maximum``, or both. The penalty is
the weighted shortfall below the minimum plus the weighted excess above the maximum; the objective is
the total penalty (lower is better). Targets load from a YAML file:

.. code-block:: yaml

   targets:
     - account: feature.Volume
       year: 0
       maximum: 500

The weights file is accepted by the command line and the configuration. Spatial constraints add a
weighted penalty to the objective (see :doc:`spatial`), disabled only by the explicit
``--spatial-override``.

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

.. autofunction:: ws4.opt.mip.bound_for

.. autoclass:: ws4.opt.telemetry.RunLogger
   :members:

.. autofunction:: ws4.opt.telemetry.read_records
