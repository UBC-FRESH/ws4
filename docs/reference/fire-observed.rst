Observed-fire contract
======================

Purpose
-------

The P156 kernel is validated against standard cases and the public FBP ellipse. This page
defines the next layer: a public observed fire with a perimeter, ignition, weather, fuel, and
terrain. The contract is read-only and records every source, unit, projection, and assumption
needed to compare a simulation without a hidden calibration step.

The first fixture is the **Dogrib fire (RWF085)**, the standard Prometheus validation case for
the Canadian FBP System. It is used only as validation evidence; the comparison harness is
P157.2.

Source and window
-----------------

- Fire: Dogrib, Northwest Territories, Canada, 2001.
- Source: Prometheus sample dataset ``Dogrib_v624.zip``, archived from the Prometheus
  distribution.
- Event: the second growth spurt, 2001-10-16 13:00 to 2001-10-17 11:52 local time.
- Observed perimeter at the start: 935 ha across two polygons.
- Observed perimeter at the end: 10,223 ha across 25 polygons, including spot fires.
- The archive contains a 5.8 MB sample dataset. The pinned fixture keeps the fuel grid,
  elevation grid, fuel lookup, hourly weather, ignition point, and two perimeter snapshots.

The source has no explicit licence file in the archive. The fixture is kept for
non-commercial validation with attribution. Replace or remove it if the source licence
requires different terms.

Projection and grid
-------------------

The fuel and elevation grids are ESRI ASCII grids:

- 357 columns by 223 rows;
- 100 m cells;
- lower-left corner at (457900, 5716800) m;
- custom NAD83 Transverse Mercator, central meridian -115°, scale factor 0.9992, false
  easting 500000 m.

The KML perimeters and ignition point are EPSG:4326. The loader transforms them into the grid
projection. The weather and perimeter timestamps are local time.

Contract
--------

``ObservedFire`` carries:

- ``fire_id``, ``name``, ``source``, ``licence``, and ``time_zone``;
- ``event_start`` and ``event_end``;
- the ignition point in longitude/latitude and grid coordinates;
- an ``ObservedGrid`` with dimensions, origin, cell size, no-data value, CRS, and bounds;
- the raw FBP fuel codes, the elevation grid, and the fuel-code lookup;
- ``ObservedPerimeter`` snapshots, each with all exterior rings, projected and geographic;
- a typed hourly weather table;
- a provenance mapping.

Each perimeter reports its time, polygon count, point count, and total area. Inner rings
(holes) are ignored; the observed fire's exterior polygons, including spot fires, are kept.

Loader and validation
---------------------

``ws4.fire.observed.load_dogrib`` validates:

- every required file is present;
- the fuel and elevation grids have the same geometry;
- every fuel code has a lookup entry, with no-data and non-fuel mapped to ``None``;
- the weather table has the expected columns, typed values, and hourly continuity;
- the weather stream covers the event window;
- the ignition point lies inside the grid;
- each perimeter overlaps the grid and has at least three exterior points.

The fixture tests cover the grid shape, fuel lookup, weather window, perimeter areas, JSON
summary, malformed grid, missing fuel file, unknown fuel code, and weather gap.

Comparison harness
------------------

``ws4.fire.comparison`` rasterizes the observed rings and the simulated burned mask onto the
same grid and reports area bias, perimeter bias, centroid distance, IoU, Sorensen, and
principal-axis orientation. ``run_dogrib_case`` starts from the observed 13:00 perimeter,
uses a homogeneous C2 fuel approximation, and runs for 402 minutes.

The base-case result is characterized, not accepted for footprint:

- area 6,259 ha vs 10,219 ha (−38.8%);
- perimeter 140.8 km vs 160.2 km (−12.1%);
- orientation error 3.1°;
- centroid distance 14.29 km;
- IoU 0.070 and Sorensen 0.131.

The coarse area, perimeter, and orientation screen passes; the centroid and overlap screen
fails. The full evidence is in ``notes/reports/p157-observed-validation.md`` and
``notes/reports/p157-dogrib-results.csv``.

Limits
------

- This is an observed-fire data contract, not yet a simulation comparison. P157.2 adds the
  metrics and tolerances.
- The event window ends at the 11:52 perimeter in this archive. The Prometheus scenario text
  describes a slightly later end; the loader records the archive's actual timestamp.
- The weather and perimeter times are local time. No daylight-saving conversion is applied.
- The observed fire includes spot fires; the P156 growth engine does not model spotting. The
  comparison must report that mismatch rather than hide it.
- The source licence is not explicit. The fixture is used with attribution for validation.

Cross-references
----------------

- :doc:`fire-behaviour`
- :doc:`fire-growth`
- :doc:`fire-benchmark`
