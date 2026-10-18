===============================
Patch size-distribution targets
===============================

A patch is a set of adjacent blocks that share a criterion — a recently disturbed stand, a band of
young forest, a productive stand. A **patch account** reports the distribution of patch **sizes**:
how much area sits in each size class, how many patches there are, and how compact they are. Target
those sub-accounts and the search has to arrange harvesting into openings of the size you choose.

Patches are **not additive over blocks**: a patch spans blocks, so a move is priced through a patch
model and patch statistics are kept only at the years a target reads. Expect a patch run to cost more
per iteration than a volume run.

Prerequisites
-------------

* A compiled dataset with **blocks** that have geometry-derived adjacency, and a topology edge list
  (see :doc:`../reference/spatial`).
* A feature to define membership: a criterion curve, and the value a block must exceed.

Procedure
---------

**1. Provide the topology.** A CSV of proximal block pairs, with the shortest distance between their
polygons. The sample estate ships one for its 8 x 8 grid:

.. code-block:: bash

   head -4 examples/estate/topology.csv

.. code-block:: text

   src_block,dst_block,distance_m
   1,2,0
   2,3,0
   1,9,0

A distance of ``0`` means the polygons touch. Building this file is a one-off GIS step; the
established ``BLOCK1,BLOCK2,DISTANCE,LENGTH`` column names are accepted too.

**2. Define the accounts.**

.. code-block:: yaml

   # examples/estate/patches.yaml
   accounts:
     - name: patch.opening
       criteria: feature.Seral.regen   # what a patch is made of: a fresh opening
       threshold: 0.5                  # a block joins when its criterion exceeds this
       size_classes: [10.0, 50.0, 150.0, 400.0, .inf]
       search_distance: 0.0            # 0 joins only blocks that literally touch

``size_classes`` are the upper bounds, in hectares. They produce the labels ``0_10``, ``10_50``,
``50_150``, ``150_400`` and ``400_9999999``, and each label carries the sub-accounts ``area``, ``size``
(the share of total patch area, in percent), ``frequency``, ``shape``, and, for an ``attractor``
class, ``attractor``.

Simulate a schedule and read the openings, which is the reliable way to see the classes:

.. code-block:: bash

   ws4 simulate --dataset tmp/estate/compiled --schedule tmp/estate/schedule.csv \
                --years 10 --topology examples/estate/topology.csv --out tmp/estate/run

.. code-block:: text

   year  patch_count  mean_patch_area  max_patch_area  le5  le10  le50  over
      0          4.0           20.125            50.4    0     1     2     1

A run's ``report_targets.csv`` prices these classes too: the run replays its incumbent through the
simulator and folds the patch accounts into the values the report reads, so a patch target shows the
same share the search priced. Simulating the same schedule is the honest cross-check, and the two
agree.

**3. Target a class.** A size class is a share, so the usual target is a floor on the share of
harvesting that lands in the class:

.. code-block:: yaml

   # tmp/howto/patch-targets.yaml
   targets:
     - account: patch.harvest.10_50.size
       year: 0
       minimum: 25
       min_weight: 2000
       shape: non_linear
       period_width: 10
     # ... one per period you care about

**4. Give the patch operators a weight.** Two operators exist for exactly this job and ship
**disabled**:

.. code-block:: bash

   ws4 optimize --dataset tmp/howto/compiled --targets tmp/howto/patch-targets.yaml \
                --years 100 \
                --topology tmp/howto/topology.csv \
                --patch-accounts tmp/howto/patches.yaml \
                --merge-weight 0.3 --split-weight 0.1 \
                --time-limit 00:05:00 --seed 1 --out tmp/howto/patches-run

``merge`` treats a **gap block** — the negative space between two proximal patches — so a small
treatment joins two patches instead of scattering harvest. ``split`` clears an **articulation
point**, separating one patch into two. Both follow the topology, so they change patch structure far
more directly than a random move. The ``cluster`` operator (``--cluster-weight``) is the third
shape-aware move: it rechooses a connected set of blocks.

**5. Read the result.** ``patch_accounts.csv`` in the run directory has one row per period, with a
column per class and sub-account:

.. code-block:: text

   year,account,value
   0,patch.harvest.10_50.size,31.2
   0,patch.harvest.10_50.frequency,7
   0,patch.harvest.10_50.shape,64.8

and ``report_targets.csv`` prices the class the way any other target is priced.

**6. The same in Python.**

.. code-block:: python

   from ws4.patch.accounts import PatchAccount

   account = PatchAccount(
       name="patch.harvest",
       criteria="feature.Volume.managed",
       threshold=20.0,
       size_classes=(10.0, 50.0, 150.0, float("inf")),
       search_distance=0.0,
   )

Pass ``patch_accounts=(account,)`` to ``Simulator.run`` for a single simulation, or point
``OptimizeConfig.patch_accounts_path`` at the YAML for a search. ``Optimizer.delta_evaluator`` takes
the same accounts, which is how a script prices a patch move
(:doc:`../getting-started/python-api`).

Troubleshooting
---------------

* **``KeyError`` on ``patch.*.size``** — the class label does not exist. The labels come from
  ``size_classes``: bounds ``10, 50, 150`` give ``0_10``, ``10_50``, ``50_150``, so a target on
  ``10_150`` is a class you never defined.
* **Every patch is a single block** — ``search_distance`` defaults to ``0``, which joins only blocks
  that share a polygon vertex. If your blocks do not touch in the topology, raise the distance; the
  ``distance_m`` column is the real gap, so a non-zero value means a road, a creek, or a
  right-of-way and the default deliberately keeps those out of a patch.
* **The patch term never fires** — the criterion may match nothing (a threshold above every block's
  value), or the period you targeted is one the search never disturbs. Check the criterion first:
  ``feature.Seral.regen`` is what a recent opening looks like, while ``feature.Seral.young`` is a
  band of young forest years later, so a patch of it is not an opening.
* **The search is slow** — patch statistics are maintained at the years a target reads, so a patch
  target on every period of a 200-year horizon keeps twenty states alive. Target the periods you
  actually care about.
* **The share is met but the map looks wrong** — a share says nothing about *where* the patches are.
  Add the spatial rules (``--max-opening-ha``, ``--min-green-up-years``, ``--core-buffer-m``) to
  constrain the openings themselves, and check ``spatial_violations.csv`` in a simulation run.
