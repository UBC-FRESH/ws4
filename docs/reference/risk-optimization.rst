Risk-aware optimization
=======================

Purpose
-------

The estate optimizer can evaluate risk-aggregated targets against a scenario ensemble through
a fast account-overlay path. One deterministic account frame is evaluated under per-scenario
account multipliers, the frames are aggregated with the existing risk layer, and the
weighted-goal objective runs on the aggregated pseudo-accounts.

This is not a process-driven stochastic landscape simulation. The full process engine remains
the auditable model; the overlay is a planning bridge until multi-fidelity ensemble evaluation
exists.

Scenario file
-------------

The optimizer reads the existing ``ws4.scenario.v1`` file. The overlay recognises
``account_multipliers``:

.. code-block:: yaml

   schema_version: ws4.scenario.v1
   scenarios:
     - scenario_id: low
       seed: 1
       overrides:
         account_multipliers:
           feature.Volume: 0.8
     - scenario_id: high
       seed: 2
       overrides:
         account_multipliers:
           feature.Volume: 1.2

Risk targets
------------

Targets must use a non-single aggregation, such as ``mean``, ``cvar_upper``, ``quantile``, or
``probability``. The risk layer creates a ``risk.<aggregation>.<index>.<account>``
pseudo-account and the optimizer prices that target.

Flow targets cannot be risk-aggregated.

CLI
---

.. code-block:: bash

   ws4 optimize ... --scenario-file scenarios.yaml

The optimizer loads the scenario set once, bypasses the per-move delta evaluator, and records
the last risk evaluation for inspection.

Limits
------

- Scenarios differ only by account multipliers; the estate simulation is shared.
- Scenario seeds do not drive process draws in this path.
- The spatial penalty is applied after the risk objective.
- Full process-driven stochastic search and multi-fidelity evaluation are later work.


Multi-fidelity verification
---------------------------

When scenarios are active, the optimizer writes ``risk_verification.json`` comparing the best
search objective with the final full-simulation risk objective. A non-zero gap is visible, not
silently corrected.

``--risk-validation-fraction`` splits the scenario ensemble into ordered training and
validation subsets and writes per-scenario and aggregated risk files plus a
``risk_validation.json`` summary. The generalization gap is the validation objective minus the
training objective. A one-scenario ensemble writes a ``skipped`` report with the reason.

The split is ordered, not random. Keep the scenario order intentional.
