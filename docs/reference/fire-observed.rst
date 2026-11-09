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
P157.2. The second fixture is the **Hay River / K'atl'odeeche fire (2023_320)**, added by P161
for an independent calibration/holdout case.

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

``ws4.fire.observed.load_dogrib`` and ``ws4.fire.observed.load_hay_river`` validate:

- every required file is present;
- the fuel and elevation grids have the same geometry;
- every fuel code has a lookup entry, with no-data and non-fuel mapped to ``None``;
- the weather table has the expected columns, typed values, and hourly continuity;
- the weather stream covers the event window;
- the ignition point lies inside the grid;
- each perimeter overlaps the grid and has at least three exterior points.

The fixture tests cover the grid shape, fuel lookup, weather window, perimeter areas, JSON
summary, malformed grid, missing fuel file, unknown fuel code, and weather gap.

Second fixture: Hay River / K'atl'odeeche (2023_320)
----------------------------------------------------

- Fire: SS005-23 / Hay River / K'atl'odeeche, Northwest Territories, May 2023.
- Perimeter and progression: CFSDS v1.1 ``2023_320_krig.tif``, day-of-burning 134–140.
  The fixture stores seven cumulative daily perimeters. The final perimeter is 2,987 ha on the
  reprojected 100 m grid; the CFSDS source area is 2,770 ha and a 22 May NWT map reports
  3,208.9 ha.
- Weather: ECCC HAY RIVER CLIMATE, climate ID 2202402, hourly local standard time,
  14 May 12:00 to 20 May 23:00.
- Fuel and elevation: FireSTARR Fuel 2023 V1.0 100 m subset, UTM zone 11N; the same archive
  provides the DEM.
- Ignition: the first-day burned centroid, not an official ignition report.
- Grid: 131 columns by 117 rows, 100 m, EPSG:26911.
- The CFSDS and FireSTARR datasets have no explicit licence file in the reviewed copies. The
  fixture is used for non-commercial validation with attribution; the raw datasets are not
  committed.

The second fixture is the data gate for P161. It is not yet used for a calibrated run; P161.2
builds the fixture, P161.3 fixes the protocol, and P161.4 runs the baseline and holdout.

Comparison harness
------------------

``ws4.fire.comparison`` rasterizes the observed rings and the simulated burned mask onto the
same grid and reports area bias, perimeter bias, centroid distance, IoU, Sorensen, and
principal-axis orientation. ``run_dogrib_case`` starts from the observed 13:00 perimeter and
can use a homogeneous C2 reference or the observed per-cell fuel, terrain, and hourly weather.

ESRI ASCII grids store row zero at the north edge. P157.5 corrected an earlier north/south
row flip; the earlier P157.2 numbers are invalid.

The documented Scenario 2 is 402 minutes, 13:00–19:42. P157.8 reproduces its main inputs:
point ignition, the 13:00 perimeter as a non-fuel break, per-cell fuel and terrain, hourly
weather, the +15° landscape wind patch, and the 280° river-polygon patch.

Scenario 2b, 402 minutes:

- area 16,241 ha vs 10,219 ha (+58.9%), including 935 ha of initial burned area;
- perimeter 281.8 km vs 160.2 km (+75.9%);
- centroid 1.77 km;
- orientation error 6.5°;
- IoU 0.385 and Sorensen 0.556.

It passes centroid, orientation, IoU, and Sorensen; it fails area and perimeter. A
1,372-minute Scenario 2b run is 27,678 ha (+170.8%), perimeter +177.7%, centroid 1.07 km,
IoU 0.304, Sorensen 0.466, and 8.0° orientation error.

Raw-wind controls: 402-minute observed-grid hourly is 17,195 ha (+68.3%), centroid 5.18 km,
IoU 0.186; 402-minute constant wind is 8,203 ha (−19.7%), centroid 9.85 km, IoU 0.206.
The full evidence is in ``notes/reports/p157-observed-validation.md`` and
``notes/reports/p157-dogrib-results.csv``. The same view is served read-only at
``/api/fire/observed/dogrib.svg``.

.. image:: /_static/fire-dogrib-view.svg
   :alt: Dogrib observed start and final perimeters over the simulated burned area
   :width: 100%

Limits
------

- The spatial growth is an independent reimplementation of published FBP and Huygens logic.
  No runnable Prometheus/FARSITE oracle was used for parity.
- Hourly FFMC uses the standard FFMC equation on hourly weather; BUI is held constant.
- Spotting is absent; the observed final contains 25 polygons, including spot fires.
- Scenario 2b overpredicts area by 59% and perimeter by 76%, so it is not an operational match.
- P160 tested the documented burning-condition thresholds and the WindNinja 2c/2d grids; the
  thresholds do not change Scenario 2b and the wind grids underburn. Hourly BUI and spotting
  remain missing.
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
