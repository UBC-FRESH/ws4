Process-conditioned schedule evaluation
=======================================

Purpose
-------

``ws4.ecosystem.evaluation`` evaluates one block-level harvest schedule through the process
engine. It maps blocks to fragments, runs fire, succession, regeneration, salvage, and
management, and returns a replayable final state and account table.

It is an evaluation path, not a replacement for the optimizer search loop.

Inputs
------

- initial cohort state and landscape edges;
- block schedule and block-to-fragment mapping;
- horizon, fire configuration, optional succession and regeneration sources;
- optional process override, harvest fraction, scenario id, and seed.

Invalid schedules, horizons, seeds, and mappings fail loudly.

Outputs
-------

``ProcessScheduleEvaluation`` returns the final state, event log, per-year values, final
accounts, and a JSON summary. ``write`` emits:

- ``process_evaluation_values.csv``;
- ``process_evaluation_accounts.csv``;
- ``process_evaluation.json``.

Final accounts include state totals, provisional volume, fire totals, harvest counts and
distinct treated area, salvage counts, and regeneration counts.

Reference case
--------------

A 3 × 3 grid of 10 ha fragments with one clearcut on fragments 1 and 2 yields two harvest
events and 20 ha of treated area. Final biomass is below the no-harvest baseline, area is
conserved, and the same schedule and seed reproduce the same summary.

Limits
------

- The final account table is a reporting view; the compiled management dataset remains
  authoritative.
- The volume bridge is provisional and uncalibrated.
- The evaluator does not search schedules or feed the optimizer objective yet.
- Harvest is a simplified clearcut-like bridge.
