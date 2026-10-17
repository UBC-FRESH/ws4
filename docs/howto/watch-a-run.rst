===========
Watch a run
===========

``ws4 watch`` runs the same search as ``ws4 optimize`` and paints the result in place: one column per
period, the target window shaded, the realized value drawn on it. It is the fastest way to see which
term is binding, and the only way to see a term that never fires.

Prerequisites
-------------

* A compiled dataset and a targets file (:doc:`write-targets`).
* A terminal. The live view repaints on a fixed heartbeat, independent of the search, so the
  iteration rate and the objective stay current between improvements.

Procedure
---------

**1. Watch one account.**

.. code-block:: bash

   ws4 watch --dataset tmp/howto/compiled --targets tmp/howto/targets.yaml \
             --account product.Harvested.CC --years 100 --period-width 10 --iterations 20000

.. code-block:: text

   ╭───────────────────────────────── ws4 watch ──────────────────────────────────╮
   │ product.Harvested.CC   objective (sum of penalties): 26.1k                   │
   │ iteration 18400/20000   1280.44 eval/s   elapsed 14.4s   seed 1   sa         │
   ╰──────────────────────────────────────────────────────────────────────────────╯

   product.Harvested.CC   Z +26.1k
      67.3k │::::::::::                     min 30.0k
            │  :::::::
            │  :::::::
            │  :::::::
     30.0k  │  #######
            └──────────
             1 2 3 4 5 6 7 8 9 10

The header carries the objective, the iteration rate, and the seed. ``Z`` is the weighted
contribution of each watched account to the objective, which is how you see which term dominates.

**2. Watch several accounts side by side.** Repeat ``--account``; each gets its own window, axis,
and title, so accounts with different units read correctly:

.. code-block:: bash

   ws4 watch --dataset tmp/howto/compiled --targets tmp/howto/level-and-flow.yaml \
             --account product.Harvested.CC --account feature.Volume.managed \
             --years 100 --period-width 10 --iterations 20000

A **share** account (a patch size class) is averaged over a period rather than summed, because
summing a share would multiply it by the period length; a volume account is summed. That is how a
volume target in cubic metres and a patch target in percent can be watched together.

**3. Print one frame.** ``--plain`` prints a single final frame instead of the live view, which is
what you want in a script or a report:

.. code-block:: bash

   ws4 watch --dataset tmp/howto/compiled --targets tmp/howto/targets.yaml \
             --account product.Harvested.CC --years 100 --period-width 10 \
             --iterations 2000 --plain

**4. Watch from Python.** ``run_watch`` takes an optimizer, the targets, the accounts, and,
optionally, a schedule to start from — which is how a **primed** run continues into a flow run
without writing files in between:

.. code-block:: python

   from ws4.opt.watch import run_watch

   run_watch(
       optimizer,
       targets,
       ["product.Harvested.CC", "feature.Volume.managed"],
       period_width=10,
       initial=primed_schedule,
   )

Troubleshooting
---------------

* **The screen sits still** — the repaint is on a heartbeat (``--refresh`` seconds, default 2), not
  on every improvement. Wait a beat; the header shows the iteration count advancing.
* **Nothing appears at all** — the live view needs a real terminal. Piping the output to a file or
  through ``tail`` shows nothing until it exits; use ``--plain`` there.
* **An account shows no window** — the account name does not match any target. Account names are
  exact: ``product.Harvested.CC``, not ``product.harvested.cc``.
* **The profile is flat immediately** — the search started from a schedule that was already flat
  (a primed run, for instance), and the band has nothing left to do.
* **The search is slow and the iteration rate low** — expected while a patch or route term is
  active: those terms are not additive, so more work happens per move
  (:doc:`../reference/performance`).
