Fire-regime benchmarks
======================

Purpose
-------

``ws4.fire.regime`` implements the published scfm fire-regime parameter and diagnostic
formulas in original Python. This is a distributional benchmark, not an event-perimeter
comparison.

Formulas
--------

- ignition rate per hectare per year;
- escape probability;
- mean and maximum escaped-fire size;
- empirical burn rate;
- per-pixel annual ignition probability;
- maximum burn cells;
- target and achieved ignitions/escapes;
- historical and simulated mean size;
- historical median size;
- fire return interval.

Reference tests
---------------

``tests/test_fire_regime.py`` reproduces the scfm toy-polygon and toy-diagnostics values:

- 180 flammable pixels of 6.25 ha;
- ignition rate 4 / (10 × 1125);
- escape probability 0.5;
- mean escaped size 75 ha;
- diagnostic target/achieved ignitions and escapes;
- achieved FRI 33.33 years and target FRI 100 years.

Limits
------

- No R/SpaDES runtime dependency.
- LandMine FRI/reburn invariants are not yet implemented.
- The benchmark is distributional, not spatial fire growth.
