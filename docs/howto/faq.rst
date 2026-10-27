==========================
Frequently asked questions
==========================

**Where do I start?**

:doc:`../getting-started/quickstart` on the command line, or
:doc:`../getting-started/python-api` if you would rather script it. Then read
:doc:`../getting-started/first-model`, which runs a complete small study.

**Why is my optimized schedule empty?**

Because nothing in the objective charged for doing nothing. An unconstrained year is free, so the
search leaves it alone. Add a floor on the years you care about, or a shape target
(:doc:`even-flow`). See :doc:`../getting-started/first-model`.

**Why does the flow term print ``inf``?**

A flow target divides by a balance — the reference period for ``even``, the period before for
``ndy``. While that balance is zero the term is infinite, by definition. Run once with a linear
volume floor so every period carries wood, then switch the flow target on. See :doc:`even-flow`.

**How do I make the search hold harvest flat?**

An **even-flow** target: a band around zero on the harvest account, plus a separate floor that pulls
the level up. The band constrains shape, the floor constrains level, and the same pair works across
scenarios. See :doc:`even-flow`.

**How do I require openings of a certain size?**

A **patch size-distribution** target, with a topology edge list. The ``merge`` and ``split``
operators exist for this and ship disabled, so give them a weight. See :doc:`patch-targets`.

**One target is eating the whole objective. What now?**

The weights are unbalanced. ``ws4 calibrate`` runs a short pilot and writes a targets file with the
weights rescaled so the terms' peaks are comparable. See :doc:`write-targets`.

**Which account do I target?**

Standing values are ``feature.*``; what treatments produced are ``product.*``; the shape of the map
is ``patch.*``; routed costs are ``route.*``; carbon is ``carbon.*``, and with an HWP config the
whole-sector balance is ``carbon.system.*`` and ``carbon.co2e.system.*``. Run one simulation on an
empty schedule and look at ``account_values.csv``: that is the complete list of what your dataset
can report.

**Why is a patch or route run so much slower?**

Patch work is confined to the years a target reads, so a patch target on every period of a long
horizon keeps many states alive. Routing is incremental for haul, maintenance, and volume, but a
**build** route account, a duplicate account, or edge contrast forces a whole-schedule pass per
evaluation. Tune without them, then add them. See :doc:`../reference/performance`.

**What about the ``--weights`` file?**

It is optional and kept for compatibility; the weights that apply are each target's
``min_weight`` and ``max_weight``, and ``ws4 calibrate`` writes a rescaled targets file for you.

**How do I repeat a run exactly?**

Record the seed, the horizon, and the whole configuration: the same inputs, seed, and code path give
the same schedule. ``summary.json`` carries the seed and the dataset manifest's digests, which is
what makes a run auditable. See :doc:`automate-a-study`.

**How do I use all my cores?**

Process-level parallelism: ``starts`` with ``workers``, or ``islands`` with ``episodes``. Threads do
not help the numeric core, which holds the GIL. See :doc:`automate-a-study`.

**Can I edit a compiled dataset by hand?**

No. It is a contract with a manifest that records the inputs' digests, and every command re-validates
it. Change the inputs or the recipe and recompile. See :doc:`prepare-a-dataset`.

**How do I add carbon to a study?**

Use a FEMIC carbon package with ``ws4 carbon``, or ``--carbon-package`` on the optimizer.
The package joins by exact track name, so rebuild it against the compiled dataset when the
matrix changes. See :doc:`run-carbon` and :doc:`../reference/carbon`.

**How do I count harvested wood products, half-life, and displacement?**

Add ``--hwp-config`` to a carbon run or ``--carbon-hwp`` to an optimization. The public
assumptions live in FEMIC's ``config/carbon/hwp.bc.yaml``. The model reports product
pools, end-of-life emissions, displacement, and whole-system carbon. The parameters are
scenario evidence, not a single calibrated truth; run a range. See
:doc:`../reference/carbon`.

**Why are carbon yield curves not the optimizer's result?**

They are an audit and interchange artifact derived from single-stand libcbm runs using the
simulated-clearcut method. The optimizer prices the exact block ledger; a curve-based LP
or surrogate is a different path and must be verified with ``ws4 carbon``. See
:doc:`run-carbon`.

**Can I compare WS4 carbon with GCBM?**

You can read and compare tabular GCBM output, but the comparison is a bridge check, not a
parity claim. GCBM and libcbm are separate CFS implementations; do not tune one to match
the other. See :doc:`../guides/limitations-and-boundaries`.

**Where do I report a problem, or read what is deliberately missing?**

The repository's issue tracker, and :doc:`../guides/limitations-and-boundaries` for what WS4 does not
do yet.
