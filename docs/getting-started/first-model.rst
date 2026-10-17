================
Your first model
================

The quickstart proved the plumbing. This page runs a **complete small study** and reads the result,
with every figure checkable by hand. It uses the same two-block example, so the arithmetic stays
visible.

The question
------------

> We need some early harvest volume, and we do not want to liquidate the natural stand.

Two accounts answer it. ``feature.Volume`` is the volume on the **natural** track, so it measures
what is left standing; ``product.Volume`` is what the treatments **produced**. Both are reported per
year, in cubic metres.

Step 1: state the question as targets
-------------------------------------

A target is an account, the first year of a period, and a bound. Write them in a file:

.. code-block:: yaml

   # tmp/getting-started/study.yaml
   targets:
     - account: feature.Volume      # keep at least 340 m3 standing at year 0
       year: 0
       minimum: 340
       period_width: 1
     - account: product.Volume      # produce at least 300 m3 at year 0
       year: 0
       minimum: 300
       period_width: 1

The two floors are deliberately close to the two arms of the trade-off: 340 is exactly what is
standing if block 1 is cleared (``2.0 * 170``), and 300 is a little less than what clearing it
produces (``3.0 * 120 = 360``).

Step 2: search
--------------

.. code-block:: bash

   ws4 optimize --dataset tmp/getting-started/compiled \
                --targets tmp/getting-started/study.yaml \
                --weights tmp/getting-started/weights.yaml \
                --years 5 --time-limit 00:00:05 --seed 1 --threads 1 \
                --out tmp/getting-started/study

The same search from Python, for comparison:

.. code-block:: python

   optimizer = Optimizer.from_dataset(
       dataset,
       OptimizeConfig(years=5, iterations=500, seed=1, targets_path="tmp/getting-started/study.yaml"),
   )
   summary = optimizer.run(Path("tmp/getting-started/study"))

Step 3: read the result
-----------------------

Four files matter. ``schedule.csv`` is the decision:

.. code-block:: text

   block_id,treatment,period
   1,CC,0
   2,CC,3

``summary.json`` says whether the search reached a feasible point:

.. code-block:: text

   incumbent_objective: 0.0
   blocks_scheduled: 2
   iterations: 500

``report_targets.csv`` says how each target fared:

.. code-block:: text

   account,year,value,minimum,maximum,penalty,status
   feature.Volume,0,340.0,340,,0.0,met
   product.Volume,0,360.0,300,,0.0,met

and ``report_accounts.csv`` summarises the whole profile:

.. code-block:: text

   account,min,max,mean,final
   feature.Volume,45.0,380.0,239.0,70.0
   product.Volume,355.0,360.0,357.5,355.0

Step 4: check it by hand
------------------------

* ``feature.Volume`` at year 0 is ``340 = 2.0 * 170``: block 1's 3.0 ha of natural track is gone, and
  block 2's 2.0 ha remains.
* ``product.Volume`` at year 0 is ``360 = 3.0 * 120``: block 1's harvest is in.
* Both floors are met, so the penalty is zero and the objective is zero.

Step 5: notice what the result does *not* say
---------------------------------------------

Block 2 is cleared at **year 3**, and that choice is arbitrary: nothing in the target set reads any
year after 0, so clearing block 2 at year 1 and clearing it at year 4 cost exactly the same. A
zero-cost search is an indifferent search.

That is the most common surprise for a new user, and the fix is to say what you care about:

* a floor on later years, to stop the search emptying them;
* an **even-flow** target, to hold the harvest profile flat, or a **non-declining** one, to stop the
  closing inventory declining (see :doc:`../howto/even-flow`);
* a **patch** target, to require that harvesting lands as openings of a certain size (see
  :doc:`../howto/patch-targets`).

Step 6: iterate
---------------

A study is a loop: state targets, search, read the *statuses* and the *penalties*, then tighten or
loosen. Two habits make the loop short:

* **Calibrate the weights** when one term drowns out the others: ``ws4 calibrate`` runs a short
  pilot search and rescales the weights so the terms are comparable
  (see :doc:`../howto/write-targets`).
* **Watch instead of waiting**, so you see which term is binding while the search runs:
  ``ws4 watch`` paints the target window live (see :doc:`../howto/watch-a-run`).

Next
----

* :doc:`../howto/index` — the task guides, including the two targets above with teeth.
* :doc:`../examples` — runnable notebooks, with output, for the same material.
* :doc:`architecture` — why the trade-offs behave the way they do.
