FBP surface fire
================

Purpose
-------

The FBP surface-fire layer implements the Canadian Forest Fire Behaviour Prediction System
surface-fire equations for the standard FBP fuel types. It consumes the FWI moisture codes
and returns surface fuel consumption, the buildup effect, the surface rate of spread, the
surface head fire intensity, and a derived flame length.

Crown fire is deliberately not part of this layer. Every result carries
``surface_only: true``; the crown fraction burned, crown fire propagation, and crown fire
intensity are P151.3.

Fuel types
----------

The supported fuel types are:

``C-1`` to ``C-7``
   Conifer types.
``D-1``
   Deciduous.
``M-1`` to ``M-4``
   Mixedwood types with conifer/dead-fir blend parameters.
``S-1`` to ``S-3``
   Slash types.
``O-1a`` and ``O-1b``
   Grass types with crown-closure and grass-load parameters.

Inputs
------

``fbp_surface_fire`` takes:

- fuel type, with or without a hyphen;
- Fine Fuel Moisture Code (FFMC);
- Buildup Index (BUI);
- ten-metre wind speed in km/h;
- optional conifer percent for M1/M2, dead-fir percent for M3/M4, crown closure for O1,
  and grass fuel load for O1.

The surface layer is **flat ground**. Slope adjustment, effective wind speed, and the
spread azimuth are part of the growth task (P151.4).

Outputs
-------

``FBPSurfaceResult`` carries:

- the Initial Spread Index (ISI);
- surface fuel consumption in kg/m²;
- the buildup effect;
- the initial surface rate of spread;
- the surface rate of spread in m/min;
- the surface head fire intensity in kW/m, ``300 × SFC × ROS``;
- Byram flame length;
- ``surface_only: true``.

Validation
----------

The implementation is validated against the ``cffdrs`` R package, the Canadian reference.
The tests cover:

- all 17 fuel types at FFMC 90, BUI 60, 10 km/h wind, and flat ground;
- a 320-point grid across C2, C3, C7, M1, and S1 with FFMC 70–95, BUI 10–100, and wind
  0–20 km/h;
- the C6 surface component separately.

Rate of spread and surface fuel consumption match within ``0.02``. The surface head fire
intensity matches the reference when the reference is a surface fire; where the reference
reports a crown fraction burned, our surface intensity is intentionally lower because crown
fuel is not included.

Example
-------

.. code-block:: bash

   python examples/fire_fbp_demo.py

The demo prints:

.. code-block:: text

   fuel  ISI    SFC kg/m2  ROS m/min  HFI kW/m  flame m
     C1   7.09      1.399       1.00     418.3     1.25
     C2   7.09      2.492       8.33    6228.3     4.31
     C4   7.09      1.752       8.79    4619.5     3.76
     M3   7.09      2.492      10.36    7743.0     4.77
     S3   7.09     21.895       5.14   33750.9     9.38
   O1A   7.09      0.350      11.75    1234.1     2.05

Limits
------

- Flat ground only. Slope adjustment and effective wind speed are P151.4.
- Surface fire only. Crown fire is P151.3.
- The C6 crown-fire ROS/HFI is not claimed; only the C6 surface component is validated.
- The VRI-to-FBP fuel-type mapping is not implemented yet.
- The FBP surface equations are validated against standard tables and the reference
  implementation, not an observed fire perimeter.

Cross-references
----------------

- :doc:`fire-behaviour`
- :doc:`fire-weather`
- :doc:`ecosystem-fire`
