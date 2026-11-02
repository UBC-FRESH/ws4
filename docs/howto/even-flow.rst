=================================
Even flow and non-declining yield
=================================

Two targets describe the **shape** of a profile rather than its level:

* **even flow** — every period is compared with a reference period (the last one by default), so the
  profile is held flat;
* **non-declining yield** (``ndy``) — every period is compared with the one before it, so the account
  is held level or rising.

Neither states a level. The usual arrangement is a **shape band** around zero with a dominant weight,
plus a set of **level aspirations** that pull the level up. The level targets do not have to be
reachable. Deliberately setting them above the achievable level is a valid and useful way to ask for
the highest even-flow harvest the estate can sustain. This guide shows both, and the priming step that
makes the terms finite.

Maximum even-flow harvest
-------------------------

This is the pattern to use when the question is **“what is the highest flat harvest profile this
estate can produce?”** rather than “hit a declared harvest level.”

Use two kinds of target on the same harvest account:

1. **A shape target.** One even-flow target covering the whole horizon, with a band, a high weight,
   and a reference period. The band charges deviation from whatever level the reference period
   realizes.
2. **Level aspirations.** One minimum target in every period. Set each minimum deliberately above the
   best level you expect the estate to achieve. The targets are not hard floors and the set is not
   “infeasible”; every period contributes a downward penalty, so the search is continuously pulled
   toward more harvest.

The level is not declared anywhere. It emerges from the competition between the shape band and the
level aspirations. If the shape target is truly dominant, the result is the **highest even-flow
harvest volume** the estate can sustain, given the other targets and constraints in the model.

An illustrative target set:

.. code-block:: yaml

   targets:
     # Shape: every period within +/-1% of period 1, weighted to dominate.
     - account: product.Harvested.CC
       period: 1
       period_width: 10
       flow: even
       flow_start_period: 1
       flow_end_period: 20
       flow_reference_period: 1
       minimum: -1
       maximum: 1
       min_weight: 10000
       max_weight: 10000
       shape: non_linear
       priority: 1

     # Level pull: the same aspiration in every period. It may be unreachable.
     - account: product.Harvested.CC
       period: 1
       period_width: 10
       minimum: 70000000
       min_weight: 1
       shape: linear
       priority: 1

     # ... repeat the level target for periods 2 through 20.

This is weighted goal programming, so keep the two roles distinct but not absolute:

* A high **weight** on the flow target makes shape dominant while leaving the level tiers active as a
  pull.
* A **priority tier** gap multiplies the lower tier by ``1e9`` per step. That is a near-lexicographic
  choice: the level pull will have almost no influence unless the flow penalties are tied. Use it only
  when that is the intent.
* If the result is flat but far too low, the shape target is overpowering the level pull, or the
  aspirations are not high enough. Raise the level targets or lower the flow/level weight ratio.
* If the result is high but ragged, the level pull is overpowering the shape target. Raise the flow
  weight.
* If the result improves for a while and then stops, check whether the flow band is already satisfied;
  a satisfied shape target has no remaining gradient, and only the level aspirations are then pulling.

Do not turn the level targets into “floors” in the feasibility sense. Their purpose is to create a
gradient across all periods; their numerical value is an aspiration, not a claim that the estate can
or must deliver it.

Prerequisites
-------------

* A compiled dataset with a harvest account and enough operable area
  (:doc:`prepare-a-dataset`).
* :doc:`write-targets` read once — the vocabulary is the same.

Procedure
---------

**1. Prime the balance.** A flow term divides by a balance: for ``even`` the reference period, for
``ndy`` the period before. While that balance is zero the term is **infinite**, which is
definitional, not a bug. Run first with only a linear level target, so every period carries wood:

.. code-block:: yaml

   # tmp/howto/level.yaml — the level target, and nothing else
   targets:
     - account: product.Harvested.CC
       period: 1
       minimum: 30000          # one target per period; here, the first
       period_width: 10
     # ... and the same for periods 2, 3, ... to cover the horizon

.. code-block:: bash

   ws4 optimize --dataset tmp/howto/compiled --targets tmp/howto/level.yaml \
                --years 100 --time-limit 00:01:00 \
                --seed 1 --out tmp/howto/primed

On a 400-block generated estate, 20,000 iterations of the level target alone leave a **ragged** profile —
the first and last periods well above the minimum, the middle ones just above it:

.. code-block:: text

   period  1      2      3      4      5      6      7      8      9     10
   m3   67,349 34,268 31,722 40,424 32,711 36,809 30,237 30,835 30,281 59,521

**2. Add the band.** Now add a flow target on the same account: zero, plus or minus one percent,
with a weight high enough that the shape is worth more than the level.

.. code-block:: yaml

   # tmp/howto/level-and-flow.yaml — the level target, plus the shape
   targets:
     - account: product.Harvested.CC
       period: 1
       minimum: 30000
       period_width: 10
     - account: product.Harvested.CC
       period: 1
       flow: even              # or: flow: ndy
       period_width: 10
       minimum: -1             # one percent below the reference period is free
       maximum: 1              # one percent above it is free
       min_weight: 10000
       max_weight: 10000
       shape: non_linear

.. code-block:: bash

   ws4 optimize --dataset tmp/howto/compiled --targets tmp/howto/level-and-flow.yaml \
                --years 100 --time-limit 00:01:00 \
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
       period: 1
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
starts at offset 50 and has no ``flow_end``.

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
  shape only; add the level aspiration, or raise it.
* **The profile is ragged and the flow term is ignored** — its weight is small next to the level's,
  or the term is priced per period against a target whose bounds the values rarely leave. Raise
  ``min_weight``/``max_weight``, or run ``ws4 calibrate``.
* **The level is right but a few periods sit just outside the band** — the band is compared with the
  reference period, not with the mean; check the reference before widening it. ``flow_reference``
  names another period to compare with.
* **The run is slow** — a flow term makes the objective re-price every period of its window on every
  move. Narrow the window with ``flow_start``/``flow_end``.
