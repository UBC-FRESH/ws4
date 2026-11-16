Decision quality under uncertainty
==================================

Purpose
-------

``ws4.opt.decision_quality`` evaluates a set of decisions across uncertainty scenarios. It
reports expected outcome, worst case, regret against the per-scenario best, rank stability, and
optional constraint satisfaction.

Contract
--------

Input is a long table with:

- a decision column;
- a scenario column;
- a finite, lower-is-better outcome column;
- an optional boolean/0-1 feasibility column.

Decision/scenario pairs must be unique. Scenario weights default to equal weights.

Outputs
-------

- expected outcome;
- worst case and best case;
- expected regret and maximum regret;
- rank range and rank stability;
- weighted constraint satisfaction.

The deterministic, robust, and minimax-regret choices are reported separately. Ties are allowed.

Containment example
-------------------

The P203 closure matrix is used as a worked example: five closure times across five weather
members. The earliest closure times dominate; later closure has higher expected area, higher
worst case, and lower rank stability.

This is a synthetic containment diagnostic, not an operational suppression decision. See
``notes/reports/decision-quality-containment.md``.
