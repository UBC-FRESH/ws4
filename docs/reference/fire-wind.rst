WindNinja wind grids
====================

Purpose
-------

The Dogrib sample distributes WindNinja terrain-adjusted wind grids for Scenario 2c
(conservation of mass) and Scenario 2d (conservation of mass and momentum). ``ws4.fire.wind``
reads the paired angle and velocity rasters, validates them, records their provenance, and
selects the nearest available direction grid for a weather step.

This module does not run WindNinja and does not treat the grids as observations.

Grid contract
-------------

A ``WindNinjaGrid`` holds:

- the domain-average direction named by the source files;
- a wind-direction grid in degrees clockwise from north;
- a wind-speed grid in km/h;
- the shared ``ObservedGrid`` geometry;
- the method label and source label.

Angle and velocity rasters must share one geometry and shape. Values must be finite; angles
must be in ``[0, 360]`` and speeds non-negative. A pair with a missing companion is rejected
rather than filled from another direction.

Selection
---------

``nearest_wind_direction`` uses circular angular distance, so 350° and 10° are 20° apart.
``wind_grid_at`` selects the nearest direction grid and returns its speed and direction at a
cell. The growth path can use those values as per-step wind inputs; it does not interpolate
between grids.

Provenance
----------

The public Dogrib archive is available from the Prometheus sample distribution. The reviewed
copy was retrieved from the `fgmfiles.spyd.com` mirror. The conservation grids are under
``conserv_mass/`` and the momentum grids are under ``conserv_mass_moment/``. Each pair is named
``windninja_<direction>_<speed>_<resolution>m_ang.asc`` and ``..._vel.asc``.

The full grids are third-party validation data with no explicit licence file in the archive.
They are used for non-commercial validation with attribution. Keep them out of the tracked
tree unless the licence position is clarified; the unit tests use small synthetic pairs.

Limits
------

- The loader does not run WindNinja or regenerate the grids.
- The full Dogrib grids are not committed.
- The growth integration and the fixed 2b/2c/2d matrix are P160.3.
- The grids are model input, not observed wind evidence.

Cross-references
----------------

- :doc:`fire-growth`
- :doc:`fire-observed`
- :doc:`fire-weather`
