BC VRI canopy-only scenario
===========================

Purpose
-------

``scripts/vri_canopy_scenario.py`` tests whether the measured FFS canopy reduction alone changes
fire behaviour on an open BC VRI stand.

Setup
-----

- 100 m grid over the MKRF VRI AOI;
- fixed C2 fuel type;
- control closure 55–70%;
- treated closure −22.9%;
- flat terrain and fixed FFMC 90, BUI 60, wind 20 km/h, 270°;
- 120-minute run.

Result
------

Control and treated both burn 228.0 ha with a 7,000 m perimeter and 16.149 m/min head ROS.

The canopy-only treatment has no effect in this C2 case. That is a negative result for crown
closure as the treatment mechanism, not a validation of a treatment.

Limits
------

- One AOI, one fuel type, one weather case.
- No surface-fuel or fuel-type conversion.
- BC CRI treatment locations are Access Only.
- No operational claim.

Report: ``notes/reports/vri-canopy-scenario.md``.
