Fire-regime risk summaries
==========================

Purpose
-------

``ws4.fire.risk`` summarizes simulated fire events as a risk distribution. It reuses the
P187 scfm formulas but reports the behaviour of a process run rather than validating a
published toy case.

Inputs
------

The summary reads event-log-like records with ``year``, ``event_type``, ``area_ha``, and
``metadata.scenario_id``. Only ``fire`` events with an area contribute. A fire event without
an area is an error.

Outputs
-------

The summary reports:

- annual burned area, fire count, escaped count, and sizes;
- total, mean, median, 90th-percentile, and maximum annual burned area;
- burn probability and annual burn rate;
- fire return interval;
- fire counts and escaped fires per year;
- mean, median, 90th-percentile, and maximum fire size;
- optional P187 target diagnostics when a target and historical sample are supplied.

A fire return interval is ``None`` when nothing burned.

Reference case
--------------

``tests/test_fire_risk.py`` uses four years, 1000 ha, 10 ha cells, and fire sizes 5, 20,
100, 1, and 2 ha. It asserts total burned 128 ha, mean annual burned 32 ha, median 14 ha,
90th-percentile 77.5 ha, burn probability 0.75, FRI 31.25 years, mean fire size 25.6 ha,
median 5 ha, and 90th-percentile 68 ha.

Limits
------

- Deterministic summary only; no fire-growth simulation or calibration.
- Target diagnostics need an explicit historical size sample.
- Separate from event-perimeter validation.
- LandMine FRI/reburn invariants remain a follow-up.
