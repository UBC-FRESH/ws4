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

Growth-trajectory diagnosis
---------------------------

P169 compared simulated daily area with observed CFSDS cumulative area.

- median day-1 ratio: 1.07x;
- every case is >2x by day 2;
- median final ratio: 12.07x at radius 2 and 11.90x at radius 1;
- all six remain >2x at both radii.

The initial growth is approximately correct. The failure is **late/continued growth**. Neighbor
radius is not the cause. The next fix should model containment/stopping or verify the
weather/FFMC sequence, not apply a global ROS multiplier.

Weather consistency
-------------------

P170 compared reanalysis-derived daily FWI with CFSDS daily FWI.

- median absolute FFMC delta: 0.77;
- median absolute BUI delta: 11.62;
- median absolute ISI delta: 0.88;
- reanalysis ISI was higher on 56 of 68 days.

FFMC and ISI are close enough that weather is not the primary cause of the 10-14x area bias.
BUI is higher, but it is not the dominant ROS driver in FBP. The next test is
containment/stopping or event timing, not weather replacement.

Terrain sensitivity
-------------------

P171 reran the six cases with flat terrain.

- median DEM area ratio: 10.35x;
- median flat area ratio: 10.35x;
- flat terrain reduced the ratio in 0 of 6 cases;
- IoU was unchanged.

Terrain is not the cause of the overprediction in this path. The remaining candidates are fuel
mapping, ROS scale, or containment/stopping.

Fuel-map sensitivity
--------------------

P172 compared per-cell fuel with the dominant homogeneous fuel.

- median per-cell area ratio: 10.35x;
- median homogeneous-dominant area ratio: 10.25x;
- homogeneous fuel reduced the ratio in 2 of 6 cases, only slightly;
- IoU changed little.

Fuel heterogeneity is not the cause. The remaining explanations are suppression/containment or
a genuine ROS-scale issue. The six cases are small fires and may be suppression-dominated.

Large-fire benchmark
--------------------

P173 ran four large fires at 500 m with the same protocol.

- median large-fire IoU: 0.238;
- median large-fire area bias: 2.89x;
- best/worst area bias: 1.67x/4.12x.

Small fires:

- median IoU: 0.096;
- median area bias: 10.35x.

The large-fire bias is far smaller, supporting small-fire suppression as a major cause. Residual
large-fire overprediction remains. The large cases use a coarse 500 m grid.
