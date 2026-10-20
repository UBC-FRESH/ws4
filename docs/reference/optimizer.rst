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
end year of its period. Targets load from a YAML file:

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
at ``year: 10`` with ``period_width: 10`` is the level for period 1, which covers years 1 to 10.

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
     # even flow: every period is compared with the reference period, here the final one
     - account: product.Yield.managed.Conif
       year: 0
       flow: even
       period_width: 10
       minimum: 0
       maximum: 0
       min_weight: 0.001
       max_weight: 0.001
     # non-declining yield over the final periods: a period may fall 1% below the one before it,
     # and rise 1% above it, before a penalty is charged. A minimum of 0 instead of -1 allows no
     # decline at all, and leaving the maximum out makes growth free.
     - account: product.Yield.managed.Conif
       year: 0
       flow: ndy
       period_width: 10
       flow_start: 150
       flow_end: 200
       minimum: -1
       maximum: 1
       min_weight: 1.0
       max_weight: 1.0

``flow.even`` gives each period its **percent difference from a reference period**,
``100 * (x_p - x_ref) / x_ref``, where the reference is the **final period of the window** unless
``flow_reference`` names another (the first year of the period to use); the reference period itself
contributes no value. ``flow.ndy`` gives each period the **percent change from the one before it**,
``100 * (x_p - x_{p-1}) / x_{p-1}``. ``flow_start`` and ``flow_end`` (in years) clip the window,
defaulting to the whole horizon, and ``period_width`` groups the years.

Both definitions were checked against the established implementation: its specification describes
comparing every period with the final one for even flow and comparing a selected period with an
offset period — the previous one for a closing inventory — and its sample scenario makes exactly
those two calls. The account is created with a factor of 100, so the values are **percentages**, and
period 0, the state before the simulation starts, is not compared. Two idioms follow from that and
are worth copying:

- **The two sides are independent, and each one is a policy.** For non-declining yield the value is
  the percent change from the previous period, so ``minimum: -1`` lets a period come in one percent
  below its predecessor before anything is charged, and ``maximum: 1`` mirrors it by letting a period
  come in one percent above. Setting only the minimum is the common case, because the decline is what
  a policy usually constrains, but the upper side is available when a case wants it. ``even`` reads
  the same way, a percent either side of its reference period.
- **A strict non-declining target is a minimum of zero with no maximum.** That is what the sample
  scenario does for a closing inventory: no decline from the period before is tolerated at all, and
  growth is free because nothing constrains the upper side. Adding a maximum there would charge the
  growth as well.
- **Every period of a non-declining window is compared, including the first**, which is measured
  against the period immediately before the window. An even-flow window compares to its reference
  instead, so its first period is an ordinary member of the band. A window that starts at year 0 has
  no period before it, so its first period contributes no value.

One difference is presentational: ``flow_end`` is **exclusive** here, while the established argument
names the last period to compare **inclusively**. A ten-period window that ends at year 200 is
``flow_end: 200`` here and a final period of 190 there.

The target's minimum, maximum, weights and shape are applied **period by period**, so
``minimum: -1`` with ``maximum: 1`` is a one-percent-either-way safe band that the scheduler is free
to move inside:

.. code-block:: yaml

   targets:
     # pull the level up; a minimum only, so it never pins the level
     - account: product.Yield.managed.Conif
       year: 0
       minimum: 2000000
       period_width: 10
     # hold the profile flat: +-1% of the final period, and far from free outside that
     - account: product.Yield.managed.Conif
       year: 0
       flow: even
       period_width: 10
       minimum: -1
       maximum: 1
       min_weight: 10000
       max_weight: 10000
       shape: non_linear

That pairing is the useful idiom: the band constrains only the *shape*, the minimum target pulls the
level up, and the pair converges on the **highest even-flow level** the forest can sustain without the
level ever being specified — so the same two targets work across scenarios.

Because both flow kinds divide by a balance, the term is **infinite while that balance is zero** — for
``even`` the reference period, for ``ndy`` every period a comparison starts from. That is definitional,
which is why a flow account is switched on only *after* the reference period is primed: run first with
a linear volume minimum above the sustainable level so that every period carries wood, then add the
flow target. `run_watch` takes an ``initial`` schedule for exactly that: continue from the primed run.

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
- ``lns`` — large-neighbourhood search: destroy a fraction of the schedule and repair it;
- ``cluster`` — rechoose a connected cluster of blocks, so a move follows the block topology and
  changes a patch-shaped set at once;
- ``merge`` — **treat the negative space between two proximal patches**: a gap block that is one
  criterion short of membership is given a chain that joins the patches;
- ``split`` — clear an articulation block, so its patch separates — the inverse of a merge.

Each operator carries a selection weight. ``toggle``, ``shift``, ``swap`` and ``lns`` are enabled
by default; ``cluster``, ``merge`` and ``split`` ship at weight zero, so a configuration must give
them a weight (``--cluster-weight``, ``--merge-weight``, ``--split-weight``, or
``OptimizeConfig.cluster_weight`` and friends) before they are selected.

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

   ws4 optimize --dataset build/compiled --targets targets.yaml \
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

Targets then read ``patch.harvest.50_250.area``, ``…size``, ``…frequency``, or ``…shape``.

Patch accounts are not additive, so the simulator reports them in ``patch_accounts.csv`` rather than in
the account values. A run's ``report_targets.csv`` folds them back in before pricing the targets, so a
patch target's status and penalty are the same ones the search saw.

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
removal/split. A patch move therefore costs a few milliseconds of patch work rather than a full
re-simulation. Patch statistics are also kept only at the years a target actually reads (the first
year of each period), because the simulation is annual while the accounting is periodic; on a
200-year, 20-period benchmark with a volume floor and a patch ramp that change alone took the search
from 62 to 310 iterations/s.

Spread connectivity
-------------------

Spread-connectivity accounts (how fragmented the fuel body a fire could run through is — see
:doc:`spatial`) are **non-additive** for the same reason patch accounts are: a compartment is a
property of the whole landscape, and no per-block delta can see it. When one is configured,
``delta_evaluator`` declines and every move is priced by a full re-simulation, so this is the slowest
spatial target to search against.

Give ``--spread-accounts`` (a YAML of definitions) with ``--block-coordinates`` (a CSV of
``block,x,y``), and set targets on the sub-accounts:

.. code-block:: yaml

   # spread.yaml
   accounts:
     - name: spread.ft
       criteria: product.Treated.managed.FT
       bearing: 225
       tolerance: 60
       search_distance: null

.. code-block:: yaml

   # targets.yaml
   targets:
     - account: spread.ft.largest_component
       year: 200
       maximum: 50000
       max_weight: 1.0

A run writes ``spread_metrics.csv`` (and, when block coordinates are available,
``spread_membership.csv`` for the map), and ``report_targets.csv`` folds the metrics back in before
pricing the targets, so the status and penalty are the ones a re-simulation gives. The option is on
``optimize``, ``watch`` and ``calibrate``. ``bearing`` is the direction the fire travels (the wind
direction), in degrees clockwise from north; ``tolerance`` is the half-width of the fast-edge cone.

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

.. autoclass:: ws4.opt.objective.Target
   :members:

.. autofunction:: ws4.opt.objective.objective

.. autofunction:: ws4.opt.objective.penalty

.. autofunction:: ws4.opt.objective.flow_values

.. autofunction:: ws4.opt.objective.flow_penalty

.. autofunction:: ws4.opt.objective.objective_terms

.. autofunction:: ws4.opt.objective.balance_targets

.. autoclass:: ws4.opt.incremental.IncrementalObjective
   :members:

.. autoclass:: ws4.opt.patch.PatchModel
   :members:

.. autoclass:: ws4.opt.operators.OperatorRegistry
   :members:

.. autofunction:: ws4.opt.operators.restore

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
