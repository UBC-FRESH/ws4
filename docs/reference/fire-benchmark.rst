Fire growth benchmark
=====================

Purpose
-------

``ws4.fire.benchmark`` compares the Huygens growth engine with the public FBP elliptical
growth model. It also runs a deterministic weather and fuel-moisture scenario ensemble and
reports empirical quantiles and exceedance probabilities.

The comparison validates geometry, not independent fire behaviour. The same FBP head rate of
spread feeds both the analytic ellipse and the growth engine. The standard-case tests
validate that head ROS against ``cffdrs`` and the R ``Rothermel`` package; this benchmark
checks that the spatial construction preserves the ellipse.

Analytic ellipse
----------------

``ellipse_metrics`` takes the head rate of spread, the FBP length-to-breadth ratio, and a
duration. It returns the head and back distances, length, width, area, and perimeter. The
perimeter uses the Ramanujan approximation.

The Huygens boundary is an ellipse with the ignition at one focus. For a head distance
``H`` and back distance ``B``, the semi-major axis is ``(H + B) / 2`` and the semi-minor
axis is ``a * sqrt(1 - e^2)``.

Benchmark matrix
----------------

The benchmark script runs five fuels (C2, C3, C7, M1, S1) at 0, 10, 20, and 30 km/h, FFMC
90, BUI 60, flat ground, and 60 minutes on a 10 m grid. It compares the measured raster
length, width, area, and perimeter with the analytic ellipse.

.. code-block:: bash

   python scripts/benchmark_fire_growth.py

The current results are:

.. list-table::
   :header-rows: 1

   * - Metric
     - Mean absolute relative error
     - Maximum absolute relative error
   * - Length
     - 1.3 percent
     - 8.4 percent
   * - Width
     - 1.9 percent
     - 8.4 percent
   * - Area
     - 7.4 percent
     - 16.4 percent
   * - Perimeter
     - 25.2 percent
     - 30.9 percent

The area error grows with wind speed because the discrete direction set still has some
anisotropy; the default 16-direction update keeps it below 17 percent on this matrix. The
perimeter is the raster cell-edge length and is systematically above the smooth ellipse;
the bias is a known raster effect, not a head-ROS error.

Scenario ensemble
-----------------

The script also runs 54 scenarios: C2, C3, and C7; FFMC 85, 90, and 95; BUI 30, 60, and 90;
and 10 and 20 km/h winds at 60 minutes. The summary is empirical, not a Monte Carlo sample
from a calibrated weather distribution.

.. list-table::
   :header-rows: 1

   * - Statistic
     - Area (ha)
   * - Minimum
     - 0.02
   * - P10
     - 0.14
   * - P50
     - 10.13
   * - P90
     - 199.85
   * - Mean
     - 51.72
   * - Maximum
     - 383.74

Exceedance probabilities: area at least 1 ha is 0.778, at least 10 ha is 0.500, at least
50 ha is 0.241, and at least 100 ha is 0.167.

``summarize_ensemble`` returns the count, mean, minimum, maximum, P10/P50/P90, and the
probability of exceeding each threshold. The thresholds and the scenario set are caller
choices.

Artifacts
---------

``python scripts/benchmark_fire_growth.py`` writes:

- ``notes/reports/p156-benchmark.csv``: one row per scenario with the kernel inputs, analytic
  ellipse, measured growth, and relative errors;
- ``notes/reports/p156-benchmark-summary.json``: the error summary and ensemble statistics.

Limits
------

- The analytic ellipse shares the head ROS with the growth engine. It does not validate the
  head ROS independently; the standard-case tests do that.
- The benchmark is homogeneous in fuel and weather. It does not exercise a DEM or a fuel
  raster.
- The perimeter is a raster cell-edge length, not a sub-cell contour.
- The ensemble is a deterministic scenario grid, not a probability model calibrated to a
  region or season.
- No observed fire perimeter is used. The phase report states this explicitly.
- C6 slope adjustment and spotting are outside the benchmark.

Cross-references
----------------

- :doc:`fire-growth`
- :doc:`fire-fbp`
- :doc:`fire-crown`
