Fire behaviour
==============

Purpose
-------

The fire-behaviour package replaces the heuristic fire-spread probability with a published
surface-fire model. The first kernel is Rothermel (1972), with the standard corrections used by
modern implementations. The inputs are explicit and metric; the outputs include rate of
spread, reaction intensity, head fire intensity, flame length, and fuel consumption.

This page specifies the fuel, moisture, and environment contracts and the Rothermel kernel. It
does not yet specify crown fire, the Canadian FBP fuel types, or landscape growth; those are
later P156 tasks.

Fuel contract
-------------

A fuel model has five fuel classes: 1-hour, 10-hour, 100-hour, live herbaceous, and live
woody. Each class carries:

- oven-dry load in tonnes per hectare;
- surface-to-volume ratio in square metres per cubic metre;
- heat content in kilojoules per kilogram.

The model adds fuel bed depth in centimetres and the dead-fuel moisture of extinction in
percent. The model type is ``S`` (static) or ``D`` (dynamic). A dynamic model transfers live
herbaceous fuel to the 1-hour dead class as the live herbaceous moisture falls below 120
percent.

The 13 Anderson standard models are included as ``ANDERSON_13``. The 16 Scott and Burgan
moisture scenarios are included as ``MOISTURE_SCENARIOS``; ``D2L2`` is the default.

Moisture contract
-----------------

``FuelMoisture`` carries the five moisture percentages. Live herbaceous moisture must be zero
or at least 30 percent, matching the Rothermel implementation's validity range. A moisture
above the dead-fuel moisture of extinction drives the dead reaction intensity to zero.

Environment contract
--------------------

``FireEnvironment`` carries:

- midflame wind speed in kilometres per hour;
- slope in percent;
- optional wind direction, aspect, elevation, temperature, and relative humidity.

Only wind and slope enter the Rothermel kernel in this slice. The remaining fields are
provenance for the FBP/weather work.

Rothermel kernel
----------------

``surface_fire(fuel, moisture, environment)`` returns a ``RothermelResult`` with:

- rate of spread in metres per minute;
- dead, live, and total reaction intensity in kilowatts per square metre;
- wind and slope coefficients;
- heat source and heat sink;
- packing ratio and relative packing ratio;
- characteristic SAV and bulk density;
- characteristic dead/live moisture and live moisture of extinction;
- fuel consumed in the flaming zone;
- Byram head fire intensity in kilowatts per metre;
- Byram flame length in metres;
- an estimated flaming residence time.

The calculation follows the model's imperial formulation internally, as the reference
implementations do, and converts the inputs and outputs to metric. The kernel is deterministic
and has no hidden random draws.

Derived intensity
-----------------

The kernel's rate of spread and reaction intensity are the validated outputs. Head fire
intensity and flame length are derived for the account and visual layers:

.. code-block:: text

   fuel_consumed_kg_m2 = total_load_kg_m2 × consumption_fraction
   intensity_kw_m = heat_yield_kj_kg × fuel_consumed_kg_m2 × ROS_m_s
   flame_length_m = 0.0775 × intensity_kw_m ^ 0.46

The default heat yield is 18,000 kJ/kg and the default consumption fraction is 0.8. These are
explicit scene/account parameters, not part of the Rothermel validation.

Standard cases
--------------

The kernel is tested against reference values generated with the R ``Rothermel`` package
(Vacchiano and Ascoli, 2015), which implements Rothermel (1972) with the Frandsen, Albini, and
Andrews corrections. The package is a validation oracle only, not a runtime dependency. The
standard 13 Anderson models at the ``D2L2`` moisture scenario, 8 km/h wind, and level ground
match within 0.01 in the reported units. The custom dynamic example and a 15-point A3
wind/slope grid also match within 0.01.

Example
-------

.. code-block:: bash

   python examples/fire_rothermel_demo.py

The demo prints a table for the 13 standard models at ``D2L2``, 8 km/h wind, and level
ground:

.. code-block:: text

   model  ROS m/min  reaction kW/m2  intensity kW/m  flame m
    A1      30.65         156.87         1221.2     2.04
    A3      39.12         550.01         6328.5     4.34
   A10       2.97        1115.88         1920.7     2.51
   A13       5.31        1847.20        16611.1     6.77

Programmatically:

.. code-block:: python

   from ws4.fire import ANDERSON_13, MOISTURE_SCENARIOS, FireEnvironment, surface_fire

   result = surface_fire(
       ANDERSON_13["A3"],
       MOISTURE_SCENARIOS["D2L2"],
       FireEnvironment(wind_kmh=8.0, slope_percent=0.0),
   )
   print(result.rate_of_spread_m_min, result.head_fire_intensity_kw_m)

Limits
------

- Only the Rothermel surface kernel is implemented. The Canadian FBP equations, crown fire,
  and landscape growth are later P156 tasks.
- The standard cases validate the kernel, not a landscape. A standard-case pass does not prove
  a fire perimeter or an observed-fire match.
- Head fire intensity and flame length are derived and are not part of the reference-case
  comparison.
- The fuel models are the 13 Anderson models. The Scott and Burgan 40 and the FBP fuel types
  follow.
- The kernel is deterministic; uncertainty belongs to the weather, moisture, and ignition
  ensemble.

Cross-references
----------------

- :doc:`ecosystem-fire`
- :doc:`ecosystem-scenarios`
