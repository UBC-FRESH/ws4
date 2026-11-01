========================
The objective
========================

There is no single thing WS4 maximizes. There is a **penalty**, and the search minimizes it: for every
target, how far the realized accounts fall outside the bounds you set, weighted, summed over targets
and periods.

That has a consequence worth internalizing: **anything you do not constrain is free**. The search will
spend an unconstrained year, an unconstrained account, or an unconstrained patch class however it likes,
because nothing charges it. An empty schedule is a common first result for exactly this reason.

Targets are aspirations, not feasibility constraints
----------------------------------------------------

The words ``minimum`` and ``maximum`` name the **hinge of a one-sided penalty**. They do not mean that
the model must remain inside a feasible interval. A minimum charges shortfall below the target and
leaves over-performance free unless a maximum is also supplied. A maximum does the reverse.

This distinction is central to forest planning:

* A target can be deliberately set **above the level the estate can actually reach**. That is not an
  infeasible target; it is a pull-up device. The penalty always has a downward gradient, so the search
  keeps allocating harvest toward the aspiration.
* A set of level targets, one per period, supplies a pull across the whole horizon. The realized level
  is an outcome of the trade-off, not a value that had to be declared first.
* A flow target supplies the **shape**. A dominant flow target, combined with level aspirations that
  are deliberately too high to satisfy, produces the highest even-flow harvest volume the estate can
  sustain. This is the **maximum even-flow harvest** pattern.
* The target set can be jointly unreachable without being invalid. “Infeasible” describes a hard
  constraint problem; WS4 is solving weighted goal programming. The result is a compromise, and the
  report exposes every target's remaining penalty so that compromise can be inspected.

Dominance is a matter of degree. Making a flow target dominant with a large weight keeps the level
aspirations active as a pull. Making it dominant with a very large priority-tier multiplier can make
the level tier almost irrelevant: the flow becomes a lexicographic first objective and the harvest
level has little influence beyond a tie-break. Both are legitimate choices, but they mean different
things. See :doc:`../howto/even-flow` for the practical pattern and
:doc:`../reference/optimizer` for weights and priority tiers.

A target has three parts: an account, a period, and an aspiration level or band. It is weighted —
`min_weight` on the shortfall, `max_weight` on the excess. `linear` charges the weighted deviation;
`non_linear` charges the weighted *squared* deviation, which is the right choice when being
approximately right matters more than being on the correct side.

Beyond a level, there are two other shapes of constraint:

* a **flow** target constrains the shape of a profile rather than its level. `even` compares every
  period with a reference period, `ndy` compares every period with the one before it, and both are
  priced per period. Paired with level aspirations, a band around zero finds the highest flat profile
  an estate can sustain without the level ever being stated.
* a **patch** target constrains the map: the size distribution of patches of a criterion feature. It is
  read at the end offset of its period, priced through a patch model, and it is what makes the search
  arrange harvesting into openings rather than simply count it.
* a **carbon** target constrains an ecosystem, product, or whole-system account. Carbon accounts use
  the same period and shape vocabulary; with an HWP configuration the system accounts add product
  storage, end-of-life emissions, and displacement. See :doc:`../reference/carbon`.

Weights are the whole tuning story. A weight that is much larger than the others makes its term
dominant, which is what you want for something that must not be violated and what you do not want by
accident. `ws4 calibrate` runs a short pilot search, records the largest penalty each target reaches,
and writes a weights file whose terms are comparable, which is the most reliable first step when a
result looks lopsided.

Where to read more: :doc:`../reference/optimizer` for the objective and the search stack,
:doc:`../howto/write-targets` for the vocabulary, :doc:`../howto/even-flow` and
:doc:`../howto/patch-targets` for the two shape constraints.
