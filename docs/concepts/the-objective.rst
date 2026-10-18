========================
The objective
========================

There is no single thing WS4 maximizes. There is a **penalty**, and the search minimizes it: for every
target, how far the realized accounts fall outside the bounds you set, weighted, summed over targets
and periods.

That has a consequence worth internalizing: **anything you do not constrain is free**. The search will
spend an unconstrained year, an unconstrained account, or an unconstrained patch class however it likes,
because nothing charges it. An empty schedule is a common first result for exactly this reason.

A target has three parts: an account, a period, and a bound. The bound can be a floor, a ceiling, or a
band, and it is weighted — `min_weight` on the shortfall, `max_weight` on the excess. `linear` charges
the weighted deviation; `non_linear` charges the weighted *squared* deviation, which is the right choice
when being approximately right matters more than being on the correct side.

Beyond a level, there are two other shapes of constraint:

* a **flow** target constrains the shape of a profile rather than its level. `even` compares every
  period with a reference period, `ndy` compares every period with the one before it, and both are
  priced per period. Paired with a floor, a band around zero finds the highest flat profile an estate
  can sustain without the level ever being stated.
* a **patch** target constrains the map: the size distribution of patches of a criterion feature. It is
  read at the first year of its period, priced through a patch model, and it is what makes the search
  arrange harvesting into openings rather than simply count it.

Weights are the whole tuning story. A weight that is much larger than the others makes its term
dominant, which is what you want for something that must not be violated and what you do not want by
accident. `ws4 calibrate` runs a short pilot search, records the largest penalty each target reaches,
and writes a weights file whose terms are comparable, which is the most reliable first step when a
result looks lopsided.

Where to read more: :doc:`../reference/optimizer` for the objective and the search stack,
:doc:`../howto/write-targets` for the vocabulary, :doc:`../howto/even-flow` and
:doc:`../howto/patch-targets` for the two shape constraints.
