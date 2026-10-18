=============
Write targets
=============

A **target** states what the schedule should achieve. This guide covers the vocabulary, the two
things that most often go wrong (a term that drowns out the others, and a target that never fires),
and how to fix both.

Prerequisites
-------------

* A compiled dataset (:doc:`prepare-a-dataset`).
* A rough idea of the accounts you care about. ``feature.*`` accounts are standing values,
  ``product.*`` accounts are what treatments produced, and ``patch.*`` accounts describe the shape of
  the map (see :doc:`patch-targets`).

Procedure
---------

**1. Write the targets.** A target names an account, the first year of a period, and a bound. The
simplest useful file has two targets: a floor on harvest, and a floor that stops the search stripping
the later years.

.. code-block:: yaml

   # tmp/howto/targets.yaml
   targets:
     - account: product.Harvested.CC     # produce at least 30,000 m3 in period 1
       year: 0
       minimum: 30000
       period_width: 10
     - account: feature.Volume.managed   # and keep at least 100,000 m3 standing in period 1
       year: 0
       minimum: 100000
       period_width: 10

**2. Decide the weights.** ``min_weight`` and ``max_weight`` say how much a deviation costs.
Defaults are ``1.0``. A weight much larger than the others makes its term dominate, which is
sometimes exactly what you want (a hard constraint you never want violated) and sometimes the bug
(one term eats the whole objective).

.. code-block:: yaml

     - account: patch.harvest.10_50.size
       year: 0
       minimum: 25
       min_weight: 2000        # a share, in percent: worth 2000 per percent below 25
       shape: non_linear       # squared, so small misses are cheap and large ones are not

**3. Choose the shape.** ``linear`` charges the weighted deviation; ``non_linear`` charges the
weighted **squared** deviation. Use non-linear when you care about being close rather than merely
on the right side, which is the usual choice for a share or a flow term.

**4. Say which years.** ``period_width`` groups years into the period a target reads: ``10`` means a
decade, ``1`` a single year. Period 0 is the state before the simulation starts, so a target at
``year: 0`` with ``period_width: 10`` is the level for the **first accounting period**, covering
years 1 to 10. Add one target per period you care about, or leave later periods out — but remember
that an unconstrained year is free, and a free year will be spent (see
:doc:`../getting-started/first-model`).

**5. Search, and read the statuses.**

.. code-block:: bash

   ws4 optimize --dataset tmp/howto/compiled --targets tmp/howto/targets.yaml \
                --years 100 --time-limit 00:02:00 \
                --seed 1 --out tmp/howto/run

``report_targets.csv`` in the run directory has one row per target: the realized value, the bounds,
the penalty, and a status of ``met``, ``below``, or ``above``. Read the penalties, not just the
statuses: a run with every status ``met`` and a large objective is meeting the targets other than the
ones you wrote.

**6. Balance the weights when one term dominates.** ``ws4 calibrate`` runs a short pilot search,
records the largest penalty each target reaches, and writes a new targets file whose weights are
rescaled so the peaks are comparable:

.. code-block:: bash

   ws4 calibrate --dataset tmp/howto/compiled --targets tmp/howto/targets.yaml \
                 --out tmp/howto/calibrated.yaml --years 100 --iterations 2000

   ws4 optimize --dataset tmp/howto/compiled --targets tmp/howto/calibrated.yaml \
                --years 100 --time-limit 00:05:00 \
                --seed 1 --out tmp/howto/run

**7. The same in Python.** Targets are ``Target`` objects, and a YAML file is just a loader for
them:

.. code-block:: python

   from ws4.opt.objective import Target, load_targets

   targets = load_targets("tmp/howto/targets.yaml")
   targets.append(Target("feature.Volume.managed", 90, minimum=100000, period_width=10))

   print(targets[0])

.. code-block:: text

   Target(account='product.Harvested.CC', year=0, minimum=30000, maximum=None, min_weight=1.0,
          max_weight=1.0, period_width=10, shape='linear', flow='', flow_start=0, flow_end=None,
          flow_reference=None)

In-memory targets are what the incremental evaluator takes
(:doc:`../getting-started/python-api`), so a script can build targets in a loop and price them
without writing a file.

Troubleshooting
---------------

* **Every status is ``met`` but the result is wrong** — the terms you did not state are free, so the
  search spent them arbitrarily. Add a target for the years and the shape you care about.
* **The search does not move** — the weights are unbalanced: one term is so expensive that every
  move is worse. Run ``ws4 calibrate``, or lower that term's weight.
* **A term never fires** — its weight is small next to the others, or the target is already
  satisfied. ``ws4 calibrate`` reports the peaks it observed, which shows you what fired.
* **A target is always ``below``** — it may be infeasible. Try it alone, with the other targets
  removed; if it is still below, the estate cannot deliver it in those years.
* **The search ignores a weights file** — ``--weights`` is optional and kept for compatibility. The
  weights that apply are the ``min_weight`` and ``max_weight`` fields above; ``ws4 calibrate`` writes
  them into a targets file for you.
