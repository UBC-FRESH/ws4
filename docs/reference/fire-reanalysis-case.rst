CFSDS hourly-reanalysis case
============================

Purpose
-------

This page records one independent CFSDS event run with hourly reanalysis weather. It is a
**depth-with-limit** case, not a station-observed hourly case.

Case
----

- CFSDS `2003_526`, event 2003-08-20 13:00 to 2003-09-04 23:00 local.
- Final observed scar: 520 ha.
- Grid: 90 x 76 cells at 100 m, EPSG:26911.
- Fuel/terrain: FireSTARR Fuel 2023 V1.0 tile 11_0.
- Weather: Open-Meteo hourly reanalysis.
- Ignition: first-day burned-cell centroid, reconstructed.
- Starting codes: FFMC 90.83, BUI 74.12.

Uncalibrated result
-------------------

.. list-table::
   :header-rows: 1

   * - Metric
     - Value
   * - Simulated area
     - 5,325 ha
   * - Observed area
     - 520 ha
   * - Area bias
     - +924%
   * - Perimeter bias
     - +496%
   * - IoU
     - 0.096
   * - Sorensen
     - 0.175
   * - Centroid distance
     - 175 m
   * - Orientation error
     - 21.6°

The model overpredicts area and perimeter. No calibration was applied.

Limits
------

- Reanalysis weather, not an on-site station.
- Daily satellite perimeters.
- Reconstructed ignition.
- One case only.

The full report is ``notes/reports/p166-reanalysis-case.md``. The close-out is
``notes/reports/p166-closeout.md``.

Multi-case distribution
-----------------------

P167 adds five more independent CFSDS reanalysis cases. All six overpredict final area.

.. list-table::
   :header-rows: 1

   * - Summary
     - Value
   * - Case count
     - 6
   * - Median IoU
     - 0.096
   * - Best IoU
     - 0.127
   * - Worst IoU
     - 0.079
   * - Median area bias
     - +9.25x
   * - Area bias range
     - +6.68x to +11.60x
   * - Overpredicted cases
     - 6 of 6

The failure is systematic across years, sizes, and fuel codes. It is a scale/shape problem, not
a single-case outlier. The full distribution is in
``notes/reports/p167-reanalysis-benchmark.md``.

Start-perimeter correction
--------------------------

P168 reran the six cases from the observed first perimeter instead of a point.

The correction did not remove the bias:

- median IoU 0.095;
- best IoU 0.097;
- worst IoU 0.079;
- area bias +8.77x to +11.60x;
- all six still overpredicted.

Point ignition was a protocol flaw, but not the dominant cause. The model fills large connected
burnable areas while the observed fires stop far short.
