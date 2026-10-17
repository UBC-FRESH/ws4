============================
Quickstart: the command line
============================

This walkthrough goes from a recipe and a fragment inventory to a compiled dataset, a simulated run,
and a search that meets a target. It uses the two-block example in ``examples/synthetic``, whose
expected numbers are written down in that directory's ``README.md``, so every figure below can be
checked by hand. The whole sequence takes seconds.

If you would rather call WS4 from Python, read :doc:`python-api` instead; the two walkthroughs do
the same work.

Install
-------

.. code-block:: bash

   python -m pip install -e ".[geo]"
   ws4 --help

``ws4`` is one command per step:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Command
     - What it does
   * - ``ws4 build``
     - Compile a recipe and a fragment inventory into a dataset.
   * - ``ws4 ingest``
     - Import an existing matrix-format dataset into the same schema.
   * - ``ws4 validate``
     - Check a dataset against its manifest and its invariants.
   * - ``ws4 simulate``
     - Replay a schedule and write a run directory.
   * - ``ws4 optimize``
     - Search for a schedule that satisfies targets.
   * - ``ws4 watch``
     - Watch realized against target values while the search runs.
   * - ``ws4 calibrate``
     - Balance target weights from a pilot search.
   * - ``ws4 report``
     - Summarise a run's accounts and target statuses.

Every command prints where it wrote its output. The dataset is the boundary: ``build`` and ``ingest``
produce one, and every other command reads only that (see :doc:`../reference/compiled-dataset`).

The example
-----------

``examples/synthetic`` is two blocks on two fragments, both on the natural track: fragment 1 is 3.0 ha
at age 40, fragment 2 is 2.0 ha at age 60. The recipe defines a growth curve per track, one clearcut
treatment (``CC``) that moves a fragment from the natural track to the managed track, a
``feature.Volume`` feature, and a ``product.Volume`` product.

With no schedule, the natural-track volume at year 0 is ``3.0 * 120 + 2.0 * 170 = 700``. Clearing
block 1 at year 0 moves that fragment onto the managed track, so the figure below should read ``340``.

Compile the dataset
-------------------

.. code-block:: bash

   ws4 build --xml examples/synthetic/recipe.xml \
             --fragments examples/synthetic/fragments.csv \
             --out tmp/getting-started/compiled
   ws4 validate --dataset tmp/getting-started/compiled

.. code-block:: text

   Built dataset → tmp/getting-started/compiled
   Dataset is valid → tmp/getting-started/compiled

Simulate a schedule
-------------------

A schedule is a CSV with ``block_id``, ``treatment``, and ``period`` columns, where the period is in
years. Clear block 1 at year 0 and replay five years:

.. code-block:: bash

   cat > tmp/getting-started/schedule.csv <<'CSV'
   block_id,treatment,period
   1,CC,0
   CSV
   ws4 simulate --dataset tmp/getting-started/compiled \
                --schedule tmp/getting-started/schedule.csv \
                --years 5 --out tmp/getting-started/sim

.. code-block:: text

   Simulation complete → tmp/getting-started/sim

The run directory holds the account values, the product values, the per-year spatial metrics when a
topology is given, and the route outputs when a route configuration is given. The head of
``account_values.csv`` is:

.. code-block:: text

   year,account,value
   0,feature.Volume,340.0
   0,product.Volume,360.0
   1,feature.Volume,360.0
   2,feature.Volume,380.0

``340.0`` is the figure from the example: the clearcut removed fragment 1's 3.0 ha of natural volume
and left ``2.0 * 170``. ``product.Volume`` records what the treatment produced.

State a target and check a run against it
-----------------------------------------

A target names an account, the first year of a period, and a bound. Targets live in a YAML file:

.. code-block:: yaml

   # tmp/getting-started/targets.yaml
   targets:
     - account: feature.Volume
       year: 0
       minimum: 700
       maximum: 700
       period_width: 1

.. code-block:: bash

   ws4 report --run tmp/getting-started/sim --targets tmp/getting-started/targets.yaml

.. code-block:: text

   Report written → tmp/getting-started/sim

``report_targets.csv`` says how each target fared, and ``report_accounts.csv`` summarises the whole
profile:

.. code-block:: text

   account,year,value,minimum,maximum,penalty,status
   feature.Volume,0,340.0,700,700,360.0,below

The status is ``below`` because clearing block 1 drops the natural volume to 340 against a floor of
700; the penalty is the shortfall.

Search for a schedule that meets it
-----------------------------------

The optimizer searches the schedules that the dataset makes operably available and reports the best
it found:

.. code-block:: bash

   printf 'weights: {}\n' > tmp/getting-started/weights.yaml
   ws4 optimize --dataset tmp/getting-started/compiled \
                --targets tmp/getting-started/targets.yaml \
                --weights tmp/getting-started/weights.yaml \
                --years 5 --time-limit 00:00:05 --seed 1 --threads 1 \
                --out tmp/getting-started/opt

It writes ``schedule.csv``, ``summary.json``, the account and product values for the incumbent, the
target report, and the telemetry log. The summary here is:

.. code-block:: text

   incumbent_objective: 0.0
   blocks_scheduled: 0
   iterations: 500
   metaheuristic: sa
   seed: 1
   status: ok

.. note::

   The incumbent is an **empty schedule**: leaving the stand alone holds ``feature.Volume`` at 700,
   which meets the floor, and no treatment can beat a penalty of zero. On a two-block landscape that
   is the whole answer — the point of the walkthrough is the plumbing, not the search.

   ``--weights`` is currently accepted and unused: weights belong to each target
   (``min_weight`` and ``max_weight``), and ``ws4 calibrate`` rescales them for you
   (see :doc:`../howto/write-targets`).

Watch a search
--------------

``ws4 watch`` runs the same search and paints the realized-versus-target window in place, one column
per period. ``--plain`` prints one frame instead of the live view:

.. code-block:: bash

   ws4 watch --dataset tmp/getting-started/compiled \
             --targets tmp/getting-started/targets.yaml \
             --account feature.Volume --years 5 --period-width 1 \
             --iterations 200 --plain

.. code-block:: text

   ╭───────────────────────────────── ws4 watch ──────────────────────────────────╮
   │ feature.Volume   objective (sum of penalties): 0                             │
   │ iteration 200/200   7858.85 eval/s   elapsed 0.0s   seed 1   sa              │
   ╰──────────────────────────────────────────────────────────────────────────────╯

   feature.Volume   Z +0
      748.1 │  ::::::::
            │####::::::
            │####::::::
          0 │##########
            └──────────
             1 2 3 4 5

Repeat ``--account`` to watch several accounts side by side, one window each. See
:doc:`../howto/watch-a-run`.

Where to go next
----------------

- :doc:`../howto/index` — task-shaped guides: targets, even flow, patches, routes, the Python API.
- :doc:`../reference/optimizer` — the objective, the operators, and the search stack.
- :doc:`../reference/simulator` — the annual engine and what a run directory contains.
- :doc:`../reference/spatial` — block topology, patch metrics, and the opening rules.
