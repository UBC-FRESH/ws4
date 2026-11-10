Fire-model validation ladder
============================

Purpose
-------

WS4 does not use one observed fire or one IoU value as a universal acceptance threshold.
Validation is tiered by the decision it supports. The machine-readable registry lives in
``ws4.fire.validation``.

The full planning note is ``notes/design/ws4-fire-validation-ladder.md``.

Tiers
-----

- **Standard** — Rothermel, FBP/cffdrs, ellipse growth, replay.
- **Event** — observed-fire perimeter reconstruction across multiple fires.
- **Risk** — burn-probability reliability, discrimination, and skill.
- **Treatment** — stand and landscape treatment response.
- **Tree** — scorch, torch, consumption, and mortality.
- **Decision** — Pareto quality, regret, constraint satisfaction, and ranking stability.

Published reference points
--------------------------

These are examples, not universal pass marks.

.. list-table::
   :header-rows: 1

   * - Benchmark
     - Value
     - Meaning
   * - WildfireAV ELMFIRE event Jaccard
     - mean 0.178
     - Multi-fire event state of practice.
   * - WildfireAV FARSITE event Jaccard
     - mean 0.176
     - Comparable multi-fire event performance.
   * - Prometheus Dogrib case 4
     - FoM 0.21
     - Difficult Canadian event at 200 m.
   * - Prometheus Dogrib case 3
     - FoM 0.568
     - Better-conditioned event.
   * - FSim top-20% BP capture
     - 56.7–79.8%
     - Burned area captured in the top 20% of mapped BP.
   * - FSim logarithmic skill
     - 0.114–0.339
     - Skill against reference models.
   * - FOFEM stand mortality
     - within ±20%
     - Most western conifer species.

Decision rules
--------------

- A single fire is context, not a universal gate.
- A multi-fire result is reported as median, spread, and worst case.
- Burn probability is judged by calibration and skill, not perimeter IoU.
- Treatment effects are judged by direction, magnitude, and ranking stability.
- Tree effects are judged by stand-level and individual-tree evidence.
- A no-go tier is recorded explicitly.

Limits
------

- Published values are not directly comparable across fires, scales, and input data.
- The event envelope is broad; a value inside it is not proof of operational skill.
- The burn-probability and tree benchmarks come from different regions and periods.
- The registry does not replace a local validation study.
