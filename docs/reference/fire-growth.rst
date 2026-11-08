Fire growth and perimeter
=========================

Purpose
-------

The growth engine turns the FBP surface and crown behaviour into a spatially explicit
perimeter. It uses a minimum-travel-time / Huygens construction on a regular cell grid: a
burning cell sends an ignition wave to each neighbour, and the travel time comes from a
directional rate of spread on an elliptical template.

This is the layer that answers where the fire is, not only how fast a point fire would run.

Site grid
---------

``SiteGrid`` carries:

- an FBP fuel type;
- rows, columns, and cell size in metres;
- FFMC, BUI, and ten-metre wind;
- slope and aspect;
- optional foliar moisture and site/day inputs;
- the M/O blend and grass parameters;
- a boolean burnable mask for water, non-fuel, or treated barriers.

The first slice is a **homogeneous** fuel grid with one weather and slope condition. A
heterogeneous fuel raster and the P144 event-log bridge are later tasks.

Slope adjustment
----------------

``effective_wind`` folds the slope into the wind vector using the FBP slope adjustment:

1. compute the surface rate of spread at zero wind;
2. multiply by the slope factor;
3. invert the FBP RSI relation to an effective ISI;
4. convert the ISI to an effective wind speed;
5. vector-add the wind and slope components.

The result is an effective wind speed and a spread azimuth. The function is validated against
the ``cffdrs`` reference on 40 wind/slope/fuel cases within 0.02 km/h and 0.1 degree. C6 slope
adjustment is explicitly unsupported and raises rather than returning a Rookermel proxy.

Growth engine
-------------

The head rate of spread comes from the validated FBP surface and crown layer. The
length-to-breadth ratio comes from the FBP ellipse relation. For each neighbour:

.. code-block:: text

   e = (LB^2 - 1) / (LB^2 + 1)
   ROS(theta) = head ROS × (1 - e) / (1 - e × cos(theta))
   arrival = current time + distance / ROS(theta)

The engine keeps the earliest arrival per cell in a priority queue. A cell is burned when its
arrival time is reached. The burned area is ``cells × cell area``; the perimeter is the exposed
cell edge length. Snapshots record time, cell count, area, and perimeter.

Non-burnable cells never ignite, so a barrier is a mask, not a penalty.

Fragment bridge
---------------

``fragment_ignition_times`` summarizes the front by dataset fragment. It returns the earliest
cell ignition time and the burned area inside each fragment, sorted by time and id.

``fragment_ignition_events`` converts those entries to the P144
``ws4.ecosystem.events.Event`` record. Because growth time is in minutes and the event clock is
in years, an ignition at minute ``t`` in year ``y`` becomes
``time = y + t / minutes_per_year``. Every event carries the fuel, weather, slope, effective
wind, head rate of spread, length-to-breadth ratio, grid cell size, and growth-model version as
attributes. The fragment log can therefore be checked against the growth field without a second
source of truth.

Validation
----------

- The slope adjustment matches ``cffdrs`` on the 40-case grid.
- No wind and no slope produce a near-circular burned area; the perimeter-to-circle ratio is
  within 25 percent on the test grid.
- Wind elongates the burned area downwind and moves the centroid downwind.
- The flat-ground wind ellipse length and width match the analytic ellipse within 10 percent.
- Wind and slope combine into one effective wind vector; the centroid moves northeast for a
  west wind and a south-facing slope.
- Slope moves the centroid upslope with zero wind.
- A non-burnable barrier stops the front.
- Snapshot area and perimeter are monotone.
- The fragment bridge returns the exact minimum cell time and burned area per fragment, and
  the event clock and attributes match the growth field.

Example
-------

.. code-block:: bash

   python examples/fire_growth_demo.py

The demo uses C2, FFMC 90, BUI 60, a 20 km/h wind from the west, and flat ground:

.. code-block:: text

   effective wind: 20.00 km/h at 90.0 deg
   head ROS: 16.15 m/min; LB: 2.57
   time min  burned cells  area ha  perimeter m
          0             1     0.01          40
         15           320     3.20         940
         30          1268    12.68        1860
         45          2859    28.59        2800
         60          5079    50.79        3720

Limits
------

- Homogeneous fuel and weather only. A heterogeneous fuel raster is a later task.
- Flat-ground slope adjustment is implemented through the effective wind, but the grid does
  not carry a DEM; slope and aspect are grid-wide.
- C6 slope adjustment is unsupported.
- No spotting or ember transport.
- The perimeter is the raster cell-edge length, not a sub-cell contour.
- The fragment bridge emits ignition events, but the P154.5 integration still has to carry the
  growth state through the accounts and the 3D viewer.
- The growth is not yet calibrated or compared to an observed perimeter; that is P154.6.

Cross-references
----------------

- :doc:`fire-crown`
- :doc:`fire-fbp`
- :doc:`fire-weather`
