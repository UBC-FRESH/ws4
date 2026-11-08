Scenario ensembles and risk targets
====================================

Purpose
-------

A deterministic estate run evaluates one schedule against one world. A scenario ensemble
evaluates the same decision against several worlds, each with its own random-tape seed and
optional process overrides. Common random numbers hold because every decision is evaluated on
the same scenario seeds, so the difference between two decisions is a decision effect rather
than a different roll of the dice.

This page specifies the scenario file, the risk aggregations, the risk pseudo-accounts, the
sample-average-approximation loop, and the out-of-sample report. The ensemble can wrap the
fire process, a compiled estate model, or a future full scenario simulator.

Scenario file
-------------

A scenario file is YAML or JSON:

.. code-block:: yaml

   schema_version: ws4.scenario.v1
   name: base
   scenarios:
     - scenario_id: s1
       seed: 11
       weight: 1.0
       overrides:
         ignition_rate_per_fragment_year: 0.02
       description: warm dry
     - scenario_id: s2
       seed: 12
       weight: 2.0
       overrides:
         ignition_rate_per_fragment_year: 0.01

``scenario_id`` (or the alias ``id``) and ``seed`` are required. ``weight`` is positive and
defaults to 1.0. ``overrides`` is a mapping the evaluator interprets; this layer only carries
it. ``description`` is optional.

Load with :func:`ws4.ecosystem.load_scenarios`. Split with ``ScenarioSet.split(train_fraction)``
to obtain a training ensemble and a validation ensemble in the original order.

Common random numbers
---------------------

The evaluator receives the scenario and must use ``scenario.seed`` for its random tape. The
same scenario set is passed to every candidate decision, so the draws are paired. A paired
comparison removes the scenario noise from the difference between decisions.

This is the mechanism behind the variance-reduction test: with the same seed for both
decisions the paired difference is exactly the decision effect; with independent seeds it is
not.

Risk aggregations
-----------------

A target opts into a scenario statistic with ``aggregation``:

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Aggregation
     - Statistic
   * - ``single``
     - No scenario dimension. This is the default and the deterministic path. It is rejected
       when the account frame carries a scenario column.
   * - ``mean``
     - Weighted mean across scenarios.
   * - ``min``
     - Smallest scenario value.
   * - ``max``
     - Largest scenario value.
   * - ``cvar``
     - Lower-tail CVaR at ``risk_alpha``: the weighted mean of the worst ``1 - risk_alpha``
       share.
   * - ``cvar_lower``
     - The explicit name for the lower-tail CVaR.
   * - ``cvar_upper``
     - Upper-tail CVaR at ``risk_alpha``: the weighted mean of the largest
       ``1 - risk_alpha`` share.
   * - ``quantile``
     - Weighted quantile at ``risk_alpha`` with linear interpolation.
   * - ``probability``
     - Weighted probability that a scenario meets the target's original minimum and maximum.
   * - ``regret``
     - Range of the scenario values, ``max - min``.

Target fields:

``aggregation``
   One of the names above. Default ``single``.
``risk_alpha``
   The tail or quantile level in (0, 1). Default 0.9.
``risk_minimum``
   An optional bound for the aggregated statistic, overriding the target's minimum.
``risk_maximum``
   An optional bound for the aggregated statistic, overriding the target's maximum.

For ``mean``, ``min``, ``max``, ``cvar``, ``cvar_lower``, ``cvar_upper``, and ``quantile``,
the effective target uses the original minimum and maximum unless a risk bound overrides it.
The aggregated value is in the account's units.

For ``probability``, the statistic is a compliance probability in [0, 1]. The original
minimum and maximum define compliance; the effective target uses ``risk_minimum`` (default
0.9) and ``risk_maximum``. For example, a minimum target of 100 with ``aggregation:
probability`` and ``risk_minimum: 0.9`` requires at least 90% of scenarios to reach 100.

For ``regret``, the statistic is the range of the scenario values. The effective target uses
``risk_maximum`` (default 0.0) and ``risk_minimum``. This is a robustness target: a smaller
range means the decision is less sensitive to the scenario.

Risk pseudo-accounts
--------------------

:func:`ws4.ecosystem.risk_account_values` turns per-scenario account values into one row per
target at the target's period end. The pseudo-account name is:

.. code-block:: text

   risk.<aggregation>.<target index>.<account>

The target index keeps two targets on the same account and aggregation from colliding. The
function also returns the **effective targets**: copies with the pseudo-account name, the risk
bounds, and ``aggregation="single"``. The existing weighted-goal objective then prices them
exactly as it prices any other target.

The per-scenario input frame has ``offset`` (or ``year``), ``account``, ``value``, and
``scenario`` columns. A target with ``aggregation="single"`` is rejected when the scenario
column is present; set ``aggregation="mean"`` or another statistic.

Flow targets are not risk-aggregated in this version. A flow penalty compares a whole profile,
not a period value, so it needs a different scenario treatment. Use ``aggregation: single`` for
a flow target and run it against one scenario, or express the profile as period targets.

Sample-average approximation
----------------------------

:class:`ws4.ecosystem.SampleAverageApproximation` evaluates a decision over an ensemble:

.. code-block:: python

   from ws4.ecosystem import (
       SampleAverageApproximation,
       ScenarioSet,
       fire_evaluator,
       synthetic_grid,
   )
   from ws4.opt.objective import Target

   _, state, edges = synthetic_grid(5, 5)
   scenarios = ScenarioSet.from_seeds([11, 12, 13])
   train, validation = scenarios.split(0.67)
   evaluator = fire_evaluator(state, edges, 10)
   targets = [
       Target(
           "fire.burned_area_ha",
           period=10,
           maximum=50.0,
           max_weight=1.0,
           aggregation="cvar_upper",
           risk_alpha=0.9,
       )
   ]
   saa = SampleAverageApproximation(train, evaluator, targets)
   best = saa.best([config_a, config_b])
   report = saa.report(best.decision, validation)
   report.write("runs/fire-risk")

The evaluator maps a decision and a scenario to an account-values frame. It must use the
scenario seed for its tape. The fire evaluator copies the initial cohort state for every run,
so a decision does not mutate the landscape.

``best`` is a finite decision-set loop: it evaluates every candidate on the training ensemble
and returns the lowest objective. For a larger decision space, call ``evaluate`` from a search
loop instead. ``report`` evaluates the chosen decision on the training and validation
ensembles and returns an :class:`ws4.ecosystem.OutOfSampleReport`.

Out-of-sample report
--------------------

``OutOfSampleReport`` carries the training and validation evaluations and the generalization
gap:

.. code-block:: text

   gap = validation objective - training objective

A positive gap means the decision looks worse out of sample. ``report.write(out_dir)`` writes:

- ``train_values.csv`` — per-scenario training values;
- ``validation_values.csv`` — per-scenario validation values;
- ``train_aggregated.csv`` — risk pseudo-accounts;
- ``validation_aggregated.csv`` — validation risk pseudo-accounts;
- ``summary.json`` — objectives, scenario counts, target penalties, and the gap.

Limits
------

- The scenario overrides are carried but not interpreted by this layer. The evaluator decides
  how to apply them.
- ``best`` evaluates a finite decision set. It is a sample-average-approximation loop, not a
  replacement for the estate optimizer's neighbourhood search.
- Flow targets are not risk-aggregated yet.
- A scenario ensemble increases evaluation cost linearly with the number of scenarios. Use
  common random numbers, a smaller training set, and a held-out validation set.
- The risk statistic is only as meaningful as the scenario distribution. A precise CVaR over a
  poorly chosen ensemble is still a poorly chosen ensemble.

Cross-references
----------------

- :doc:`ecosystem-fire`
- :doc:`ecosystem-package`
- :doc:`optimizer`
- :doc:`../concepts/the-objective`
