=================================
Even flow and non-declining yield
=================================

Two targets describe the **shape** of a profile rather than its level:

* **even flow** — every period is compared with a reference period (the last one by default), so the
  profile is held flat;
* **non-declining yield** (``ndy``) — every period is compared with the one before it, so the account
  is held level or rising.

Neither states a level. The usual arrangement is a **band** around zero with a high weight, plus a
separate floor that pulls the level up, which is what makes the same two targets work across
scenarios. This guide shows both, and the priming step that makes the terms finite.

Prerequisites
-------------

* A compiled dataset with a harvest account and enough operable area
  (:doc:`prepare-a-dataset`).
* :doc:`write-targets` read once — the vocabulary is the same.

Procedure
---------

**1. Prime the balance.** A flow term divides by a balance: for ``even`` the reference period, for
``ndy`` the period before. While that balance is zero the term is **infinite**, which is
definitional, not a bug. Run first with only a linear floor, so every period carries wood:

.. code-block:: yaml

   # tmp/howto/level.yaml — the floor, and nothing else
   targets:
     - account: product.Harvested.CC
       year: 0
       minimum: 30000          # one target per period; here, the first
       period_width: 10
     # ... and the same for years 10, 20, ... to cover the horizon

.. code-block:: bash

   ws4 optimize --dataset tmp/howto/compiled --targets tmp/howto/level.yaml \
                --weights tmp/howto/weights.yaml --years 100 --time-limit 00:01:00 \
                --seed 1 --out tmp/howto/primed

On a 400-block generated estate, 20,000 iterations of the floor alone leave a **ragged** profile —
the first and last periods well above the floor, the middle ones just above it:

.. code-block:: text

   period  1      2      3      4      5      6      7      8      9     10
   m3   67,349 34,268 31,722 40,424 32,711 36,809 30,237 30,835 30,281 59,521

**2. Add the band.** Now add a flow target on the same account: zero, plus or minus one percent,
with a weight high enough that the shape is worth more than the level.

.. code-block:: yaml

   # tmp/howto/level-and-flow.yaml — the floor, plus the shape
   targets:
     - account: product.Harvested.CC
       year: 0
       minimum: 30000
       period_width: 10
     - account: product.Harvested.CC
       year: 0
       flow: even              # or: flow: ndy
       period_width: 10
       minimum: -1             # one percent below the reference period is free
       maximum: 1              # one percent above it is free
       min_weight: 10000
       max_weight: 10000
       shape: non_linear

.. code-block:: bash

   ws4 optimize --dataset tmp/howto/compiled --targets tmp/howto/level-and-flow.yaml \
                --weights tmp/howto/weights.yaml --years 100 --time-limit 00:01:00 \
                --seed 1 --out tmp/howto/even

Continuing from the primed schedule for a further 20,000 iterations flattens it, and the flow
penalty falls to zero:

.. code-block:: text

   period  1      2      3      4      5      6      7      8      9     10
   m3   35,348 34,821 35,320 35,410 35,478 35,272 35,448 34,965 35,115 35,139
   flow penalty  0.0

Note what the band did and did not promise: the spread is 34,821 to 35,478, which is **within one
percent of the reference period** (the last one, 35,139) — not within one percent of the mean. That
is why the penalty is zero.

**3. Non-declining instead of even.** ``ndy`` compares each period with the period before it, so the
same band tolerates a one-percent **decline**:

.. code-block:: yaml

     - account: feature.Volume.managed
       year: 0
       flow: ndy
       period_width: 10
       flow_start: 50          # the last five periods, say
       minimum: -1             # one percent below the previous period is free
       min_weight: 10000
       shape: non_linear

Omit ``maximum`` to leave growth free, which is the strict closing-inventory form; set
``maximum: 1`` to charge a rise as well, which is occasionally what a case wants. Every period of
the window is compared, including the first, which is measured against the period immediately before
the window. ``flow_end`` is **exclusive**, so a window of the last five decades of a 100-year horizon
starts at year 50 and has no ``flow_end``.

**4. The same in Python.** The flow keys are fields on ``Target``:

.. code-block:: python

   from ws4.opt.objective import Target

   band = Target(
       "product.Harvested.CC",
       0,
       flow="even",
       period_width=10,
       minimum=-1.0,
       maximum=1.0,
       min_weight=10_000.0,
       max_weight=10_000.0,
       shape="non_linear",
   )

**5. Watch it converge.** The band is the clearest thing to watch, because the profile snaps flat
within a few thousand iterations while the *level* keeps climbing:

.. code-block:: bash

   ws4 watch --dataset tmp/howto/compiled --targets tmp/howto/level-and-flow.yaml \
             --account product.Harvested.CC --years 100 --period-width 10 --iterations 20000

Troubleshooting
---------------

* **The flow penalty is ``inf``** — a balance is zero. Prime first (step 1); if it stays infinite,
  the reference period has no wood at all, which usually means the floor is too high or the wrong
  account is named.
* **The profile is flat but very low** — the band worked and the level did not. The band constrains
  shape only; add the floor, or raise it.
* **The profile is ragged and the flow term is ignored** — its weight is small next to the level's,
  or the term is priced per period against a target whose bounds the values rarely leave. Raise
  ``min_weight``/``max_weight``, or run ``ws4 calibrate``.
* **The level is right but a few periods sit just outside the band** — the band is compared with the
  reference period, not with the mean; check the reference before widening it. ``flow_reference``
  names another period to compare with.
* **The run is slow** — a flow term makes the objective re-price every period of its window on every
  move. Narrow the window with ``flow_start``/``flow_end``.
