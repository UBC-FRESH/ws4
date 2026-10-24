Optimizer
=========

The optimizer searches for a schedule that meets a set of goal-programming targets over a compiled
dataset. It is a layered, pluggable stack (``notes/adr/0007``): an objective, a problem adapter, a
registry of neighbourhood operators, and a metaheuristic solver. Every search records its seed, so a
result is reproducible.

Objective
---------

A target names one account and one accounting **period**, with a ``minimum``, a ``maximum``, or both.
**The simulation step is one year and is not configurable.** Treatments, growth, transitions and road
events are all simulated annually, at a simulation *offset* (offset 0 is the first year); the
**account** time step is a whole number of years — the period length — and is what ``period_width``
sets (default 1). Five and ten years are the convention in forest planning; any whole multiple of a
year is accepted. For an additive account (volume, area, a count) the account value for the period is
the sum of its offsets, compared to the levels, so a decade target is ``period_width: 10``; the penalty
is the weighted shortfall below the minimum plus the weighted excess above the maximum, and the
objective is the total penalty (lower is better). A **patch** account is a snapshot of the map rather
than an additive quantity, so a patch target is read at the end offset of its period. Targets load from
a YAML file:

.. code-block:: yaml

   targets:
     - account: feature.Volume
       period: 0
       maximum: 500
     - account: product.Yield.managed.Conif
       period: 1
       minimum: 800000
       maximum: 800000
       period_width: 10
     - account: patch.harvest.10_50.size
       period: 1
       minimum: 100
       min_weight: 10000
       shape: non_linear

**Period numbering**: **period 0 is the zero-length pre-simulation snapshot at offset -1**, and periods
**1 to N** are the accounting periods the targets are set on. A target at ``period: 1`` with
``period_width: 10`` reads offsets 0 to 9; period 2 reads offsets 10 to 19, and so on. The **year** is a
display label only: it is the year the period ends on (``offset + 1``), so period 1 with width 10
displays as the decade ending in year 10. ``year`` remains accepted for older target files, but write
``period``.

**Flow targets** express even flow or non-declining yield without pinning the level, which is the
established way to state them: the flow target is set to zero with a weight, and a separate target on
the same account sets the level.

.. code-block:: yaml

   targets:
     # the level
     - account: product.Yield.managed.Conif
       period: 1
       minimum: 900000
       maximum: 1400000
       period_width: 10
     # even flow: every period is compared with the reference period, here the final one
     - account: product.Yield.managed.Conif
       period: 1
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
       period: 1
       flow: ndy
       period_width: 10
       flow_start_period: 16
       flow_end_period: 19
       minimum: -1
       maximum: 1
       min_weight: 1.0
       max_weight: 1.0

``flow.even`` gives each period its **percent difference from a reference period**,
``100 * (x_p - x_ref) / x_ref``, where the reference is the **final period of the window** unless
``flow_reference_period`` names another; the reference period itself contributes no value.
``flow.ndy`` gives each period the **percent change from the one before it**,
``100 * (x_p - x_{p-1}) / x_{p-1}``. ``flow_start_period`` and ``flow_end_period`` (inclusive) clip
the window, defaulting to the whole horizon, and ``period_width`` sets the years per period.

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
  instead, so its first period is an ordinary member of the band. A window that starts at period 0 has
  no period before it, so its first period contributes no value.

``flow_end_period`` is **inclusive**; the legacy year-based ``flow_end`` key remains **exclusive**.
A ten-period window covering periods 1 to 10 is ``flow_end_period: 10`` (or legacy
``flow_end: 101``).

The target's minimum, maximum, weights and shape are applied **period by period**, so
``minimum: -1`` with ``maximum: 1`` is a one-percent-either-way safe band that the scheduler is free
to move inside:

.. code-block:: yaml

   targets:
     # pull the level up; a minimum only, so it never pins the level
     - account: product.Yield.managed.Conif
       period: 1
       minimum: 2000000
       period_width: 10
     # hold the profile flat: +-1% of the final period, and far from free outside that
     - account: product.Yield.managed.Conif
       period: 1
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

Normalization and priority tiers
--------------------------------

Targets with different units compete on different scales: a volume floor in cubic metres
can dominate a patch-size share or a cost ceiling. Two opt-in target fields make the
trade-off explicit.

``normalization: auto`` divides the target's weighted penalty by the larger absolute
minimum/maximum, floored at one. ``normalization: none`` is the default and keeps the old
behaviour. The scale is recorded in ``report_targets.csv`` beside the raw and normalized
penalty.

.. code-block:: yaml

   targets:
     - account: product.Yield.managed.Conif
       period: 1
       period_width: 10
       minimum: 800000
       normalization: auto
     - account: patch.harvest.10_50.size
       period: 1
       minimum: 10
       normalization: auto

``priority`` is a positive integer tier. Targets at the same tier add normally. When more
than one tier is present, a lower-priority tier is multiplied by ``PRIORITY_SCALE`` per step
(``1e9``), so a small higher-priority penalty outranks a larger lower-priority one in the
scalar search. This is a priority-weighted objective, **not a certified lexicographic
solve**; the run report still carries every target's raw and normalized penalty so a
reviewer can inspect the trade-off. The default priority is one, which leaves the current
objective unchanged.

.. code-block:: bash

   ws4 optimize --dataset build/compiled --targets targets.yaml --out opt

The report columns are ``raw_penalty``, ``penalty`` (normalized), ``scale``,
``normalization``, and ``priority``. The incremental evaluator and the MIP/LP option model use
the same scale; sensitivity reports the effective normalized marginal.

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

The solvers are simulated annealing (``sa``), tabu search (``tabu``), iterated local search
(``ils``), and threshold accepting (``threshold``), selected by ``--engine``
(``OptimizeConfig.metaheuristic``). A run may use multiple starts (``OptimizeConfig.starts``), serial
or across a process pool (``OptimizeConfig.workers``), keeping the best.
``OptimizeConfig.warm_start`` seeds the search from each block's first candidate.

Threshold accepting (``--engine threshold``) accepts an improving move always, and accepts a
worsening move while its increase is no larger than the current **threshold**. The threshold is
multiplied by the cooling factor each iteration; ``--threshold`` sets the initial value and
``--cooling`` sets the factor. It is simpler to explain and tune than SA and is competitive on
spatial harvest scheduling. Like SA, it honours ``--patience`` and ``--reversion``.

Seeding a target by construction
--------------------------------

``--seed-greedy`` builds a starting schedule from the targets instead of relying on the
one-block moves to find hundreds of them. In the default mode the declared **floors** are the
goal: candidates are ranked by the penalty they remove per unit of the declared cost
ceilings, and taken until the ceilings would be breached. This is the aggregate-area case
(#133/P14).

    ws4 optimize --dataset build/compiled --targets targets.yaml --seed-greedy ...

A **reduction goal** uses ``--seed-account`` instead. The named target must be active and
have a ``maximum``; the other maximum targets are its cost ceilings. Candidates are ranked
by the penalty they remove from that target per unit of cost, and taken until the target is
met or the budget is exhausted. This is the hazard-shaped case:

    ws4 optimize --dataset build/compiled --targets hazard.yaml \
                 --seed-greedy --seed-account feature.FuelHazard ...

The seed is a starting point, not an enforcement: the search remains free to soften any
bound. The goal seed is exact for the simulator's account deltas, so its result is checked
by the same ``report_targets.csv`` as a normal run.

For a large feature goal with product cost ceilings, the seed first shortlists the 40,000
blocks with the cheapest direct feature-curve reduction per dollar, then prices the
shortlisted chains exactly. The screen is a heuristic for speed; it never substitutes an
estimated value for the reported result. Other goal shapes use the full candidate set.

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

A continuous search can stop on **stability** instead of a fixed budget: ``OptimizeConfig.patience``
(``--patience``) ends a start after that many iterations without an incumbent improvement, and
``0`` disables the rule. The run summary records ``patience`` beside ``iterations`` and
``time_limit_reached``; the web player exposes the same field as **Patience**. The stability stop is
deterministic for a seed because it counts iterations, not wall-clock time.

A search can also **revert** to its incumbent: ``OptimizeConfig.reversion`` (``--reversion``)
resets the current solution to the best schedule every *N* accepted moves, then continues from
there. ``0`` disables it. Reversion is a cheap intensification step that recovers a search which
has wandered into a poor neighbourhood; the run summary records ``reversion`` with the other
search settings. It is applied by SA, tabu, and ILS.

The mixed-integer layer (``ws4.opt.mip``) solves an option-selection MILP (HiGHS via
``scipy.optimize.milp``) for a penalty **lower bound** and a candidate schedule. Enabling
``OptimizeConfig.mip_bound`` (``--mip-bound``) records the bound, the gap, and the bound status in the
summary. With ``--topology`` and ``--max-opening-ha`` the bound also enforces the stand-centred
opening constraints, which tighten it as the cap falls.

Constraint strategies
---------------------

The spatial rules are **penalties** by default: an opening, green-up, or core-area violation adds a
weighted penalty to the objective, and the search may trade it against the targets. Two opt-in
policies make the rules hard:

.. code-block:: bash

   ws4 optimize --dataset build/compiled --targets targets.yaml --out opt \
     --topology topology.csv --max-opening-ha 40 --min-green-up-years 3 \
     --constraint-strategy reject

``penalize`` is the default. ``reject`` refuses a move that would leave the schedule infeasible.
``repair`` first tries a one-block local repair — drop an added block, restore a removed one, or
restore a modified chain — and rejects the move if the result is still infeasible. The guard wraps
the operator registry, so SA delta, SA, tabu, ILS, and threshold all see the same policy.

An infeasible warm start or construction seed is made feasible before the search by removing the
blocks in violating patches or green-up pairs. The run summary records ``constraint_strategy``,
``constraint_stats`` (proposed, feasible, rejected, repaired, initial removals), and
``constraint_feasible``. The run directory also contains ``constraint_report.json`` with the same
counts and the final violation records. ``penalize`` keeps the scalable incremental penalty path;
``reject`` and ``repair`` evaluate the full schedule per proposal, so use them on a constrained
subproblem or when hard feasibility matters more than throughput.

Flow ceiling
------------

``scripts/max_flow.py`` binary-searches a constant per-period volume floor. It replaces the targets
on the chosen account with one floor per accounting period, keeps the other targets, and probes the
existing optimizer at each level. A probe passes when every period meets the level within a relative
tolerance and the optimizer reports no spatial violations.

.. code-block:: bash

   python scripts/max_flow.py \
     --dataset build/compiled --targets targets.yaml \
     --account product.Yield.managed.Conif --out runtime/max-flow \
     --years 100 --period-width 10 --iterations 300 --probes 10 \
     --topology topology.csv --max-opening-ha 40 --constraint-strategy reject \
     --flow ndy --flow-tolerance 0

The optional ``--flow ndy|even`` adds the matching flow target to every probe; the report
keeps floor feasibility and flow feasibility separate and records the worst period change.
The high bound is an additive envelope: for each block, the best candidate contribution per period,
summed over blocks. It is an upper bound, not a schedule. The **advisory ceiling** is the highest
level a finite probe verified; the output contains ``max_flow.json``, ``max_flow.md``,
``probe-config.json``, the probe run directories, and ``best-schedule.csv``. A zero ceiling still
writes a valid report. The ceiling is not a certified maximum.

Run
---

.. code-block:: bash

   ws4 optimize --dataset build/compiled --targets targets.yaml \
                --threads 8 --seed 42 --out opt

When a route configuration is given (``OptimizeConfig.route_config_path`` or
``--route-config``), the objective is evaluated with the route model, and the route accounts and
duplicate accounts (see :doc:`roads`) are resolved into the account values, so targets can be set on
accounts such as ``route.Total.haul``.

Validation sweep
----------------

``scripts/validate_search.py`` runs the same targets, horizon, and iteration budget through several
engines and seeds, then reports the distribution of incumbents. It is orchestration of the same
``Optimizer`` the CLI uses, so a record can be reproduced with the equivalent ``ws4 optimize``
command. The report is advisory; it does not change a schedule.

.. code-block:: bash

   python scripts/validate_search.py \
     --dataset build/compiled --targets targets.yaml \
     --engines sa,tabu,ils --seeds 1,2,3 --iterations 500 --years 50 \
     --out runtime/validation

Use ``--reversion`` to include the reversion interval in every run, so a sweep can compare a
reverted search with the plain one. The JSON records each run's objective, zero-penalty status,
output directory, reversion interval, and (with ``--mip-bound``) the lower bound and gap. The Markdown table reports runs, best, mean, median, worst,
and population standard deviation per engine. Use it before a release or a benchmark claim: a single
seed is an anecdote, and a single engine is not a comparison.

Target sensitivity
------------------

``scripts/sensitivity.py`` reads a completed run's ``report_targets.csv`` and the target file that
produced it, then reports each target's distance to its nearest bound, whether it is binding, and the
per-unit objective weight that applies when a bound is relaxed. It is advisory and does not change a
schedule.

.. code-block:: bash

   python scripts/sensitivity.py --run opt --targets targets.yaml --out opt/evidence

A missed target has a marginal cost per unit; a target with slack is not controlling the plan. A
binding target exactly at its bound with zero shortfall has no penalty to remove, so its marginal is
also zero. The JSON and Markdown reports are suitable for a plan review or an AAC negotiation record.

Search portfolio and Pareto front
---------------------------------

The search minimizes one weighted-goal penalty. A decision review often needs the
neighbouring answers too, so ``scripts/portfolio.py`` re-runs the existing optimizer over
a grid of target-weight factors. Every member keeps its objective and realized metrics;
``ws4.opt.archive`` keeps the elites and filters the nondominated front.

.. code-block:: bash

   python scripts/portfolio.py \
     --dataset build/compiled --targets targets.yaml --out runtime/portfolio \
     --vary "product.Yield.managed.Conif=0.5,1,2;feature.Old=1,2" \
     --metrics product.Yield.managed.Conif,feature.Old \
     --directions "product.Yield.managed.Conif=max;feature.Old=max" \
     --seeds 1,2,3 --iterations 500 --years 50

A factor multiplies the matching targets' ``min_weight`` and ``max_weight``; the bounds and
the other targets are unchanged. An ``account@period`` key varies one period. The metrics
read ``account_values.csv``: a bare name is the last offset, ``name@sum`` sums the horizon,
and ``name@<offset>`` reads one year. The output directory contains the member runs,
``portfolio.json``, ``portfolio.md``, ``front.csv``, and an ``archive/`` directory with the
manifest and one schedule CSV per archived elite.

The front is a finite grid under a fixed budget and seed set. It is advisory, not a
certified optimum, and a weight vector that reaches the same metric point as another keeps
the lower scalar objective.

Tuner
-----

``scripts/tune.py`` runs a grid or a seeded random sample over a small set of
``OptimizeConfig`` fields. Every candidate uses the same dataset, targets, seeds, and
iteration budget; the report ranks by best and then median objective, so one lucky seed
does not choose the winner. Path fields and the evaluation seed are not tunable.

.. code-block:: bash

   cat > runtime/space.json <<'JSON'
   {"temperature": [100, 500, 1000], "cooling": [0.9, 0.95, 0.99]}
   JSON
   python scripts/tune.py \
     --dataset build/compiled --targets targets.yaml --space runtime/space.json \
     --out runtime/tuning --seeds 1,2,3 --iterations 300 --years 50

Use ``--mode random --budget 12`` to sample instead of crossing the grid. The directory
contains one run per candidate and seed, ``tuning.json``, ``tuning.md``, and ``best.json``
for the winning parameters. A failed seed is named in the report rather than aborting the
sweep. The ranking compares a finite budget; it is not an optimality claim.

LP dual and reduced-cost sensitivity
------------------------------------

``scripts/lp_sensitivity.py`` relaxes the option-selection model's binary variables to
``[0, 1]`` and solves the same target and opening rows with HiGHS through
``scipy.optimize.linprog``. The LP objective is a lower bound on the mixed-integer penalty.
Each target row reports a **dual**: the objective reduction from relaxing its bound by one
unit (lowering a minimum or raising a maximum). Each option variable reports its LP value
and reduced cost.

.. code-block:: bash

   python scripts/lp_sensitivity.py \
     --dataset build/compiled --targets targets.yaml --out runtime/lp \
     --years 10 --limit-blocks 2000 --top 20

Use ``--limit-blocks`` to declare a subproblem; a full landscape is much larger than this
report is intended to solve. ``--topology`` and ``--max-opening-ha`` add the same
stand-centred opening rows as the MIP bound. The JSON and Markdown are advisory: they price
the relaxation, not a schedule, and a zero dual on a non-binding row is expected.

Watch
-----

``ws4 watch`` runs the same search and paints the realized-versus-target window of an account in
place: one column per period, the minimum/maximum target band shaded, and the realized value drawn
over it, coloured by status (green inside the window, red below the minimum, blue above the
maximum). Targets are per period; the view groups offsets into periods of ``--period-width`` years, so
per-period levels that sum to a periodic target read as the periodic window. ``--plain`` prints one
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
re-simulation. Patch statistics are also kept only at the offsets a target actually reads (the end
offset of each period), because the simulation is annual while the accounting is periodic; on a
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
       period: 20
       period_width: 10
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
     - The incumbent schedule (``block_id,treatment,offset``).
   * - ``summary.json``
     - The run summary: objective, iterations, patience, reversion, seed, metaheuristic, operators, block count,
       status, time-limit flag, dataset reference.
       and the dataset manifest.
   * - ``account_values.csv``, ``product_values.csv``
     - The simulated account and product values for the incumbent schedule.
   * - ``report_accounts.csv``, ``report_targets.csv``
     - The account summary and the per-target status, including target kind and normalized penalty.
   * - ``ending_inventory.csv``
     - The final feature-inventory value per account at the last offset.
   * - ``telemetry.jsonl``
     - A run header and one record per search step.

Run manifest and data quality
-----------------------------

Every run writes two review artefacts beside the summary:

- ``run_manifest.json``: the ws4 version and Git revision (when available), the dataset reference
  and source hashes, the full ``OptimizeConfig``, the seeds, the Python/package environment, and a
  reproduce command. The command repeats the principal settings; the full configuration is in the
  manifest.
- ``data_quality.json``: the dataset manifest metadata, Parquet table row counts, target-account
  coverage, and a list of explicit unknowns and model limitations. The run summary carries a compact
  ``data_quality`` block and the report path.

The quality status distinguishes **not supplied** from **checked and good**. A dataset with no
metadata reports ``unknown`` and names the missing inventory-vintage/imputation/coverage fields
rather than treating an empty block as a pass. Derived accounts (``patch.*``, ``route.*``,
``spread.*``) are reported separately because they are not rows in ``accounts.parquet``.

Scenario comparison
-------------------

``scripts/compare_scenarios.py`` reads completed runs and compares them over one landscape:

.. code-block:: bash

   python scripts/compare_scenarios.py \
     --run base=runtime/base --run dense=runtime/dense \
     --metric product.Yield.managed.Conif:max --metric feature.Old:min \
     --out runtime/compare

Each ``--run`` takes ``label=path``. The output contains ``scenarios.json``, ``scenarios.md``,
``scenario_runs.csv``, ``scenario_targets.csv``, ``scenario_accounts.csv``, ``scenario_ending.csv``,
and ``scenario_flows.csv``. With ``--metric`` the
command also reports the nondominated front over those accounts; an account missing from a run keeps
that run off the front rather than inventing a value. A missing summary, target report, or constraint
report is shown as unavailable, not as passing.

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

.. autofunction:: ws4.opt.objective.raw_penalty

.. autofunction:: ws4.opt.objective.normalization_scale

.. autofunction:: ws4.opt.objective.priority_total

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

.. autoclass:: ws4.opt.constraints.ConstraintGuard
   :members:

.. autofunction:: ws4.opt.max_flow.run_max_flow

.. autofunction:: ws4.opt.repro.write_reproducibility

.. autofunction:: ws4.opt.repro.dataset_quality

.. autofunction:: ws4.opt.scenarios.compare_scenarios

.. autofunction:: ws4.opt.max_flow.high_bound

.. autofunction:: ws4.opt.max_flow.flow_feasibility

.. autofunction:: ws4.report.ending_inventory

.. autofunction:: ws4.opt.mip.relaxation_for

.. autoclass:: ws4.opt.mip.LpResult
   :members:

.. autoclass:: ws4.opt.archive.Elite
   :members:

.. autoclass:: ws4.opt.archive.EliteArchive
   :members:

.. autofunction:: ws4.opt.archive.pareto_front

.. autofunction:: ws4.opt.portfolio.run_portfolio

.. autofunction:: ws4.opt.tune.run_tuning

.. autoclass:: ws4.opt.telemetry.RunLogger
   :members:

.. autofunction:: ws4.opt.telemetry.read_records
