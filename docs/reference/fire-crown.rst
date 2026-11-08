Crown fire
==========

Purpose
-------

The crown-fire layer adds the vertical dimension to the FBP surface fire: does the surface
fire ignite the canopy, how much of the canopy burns, and how does the crown fuel change the
head fire intensity?

The initiation threshold is Van Wagner's critical surface intensity. The crown fraction
burned and the C6 crown rate of spread are the Canadian FBP formulations. A separate Van
Wagner active-crown threshold is available when a canopy bulk density is supplied.

Initiation
----------

Van Wagner's critical surface intensity is:

.. code-block:: text

   CSI = 0.001 × CBH^1.5 × (460 + 25.9 × FMC)^1.5

where ``CBH`` is the crown base height in metres and ``FMC`` is the foliar moisture content in
percent. The critical surface rate of spread is ``CSI / (300 × SFC)``.

The FBP crown fraction burned is:

.. code-block:: text

   CFB = 1 - exp(-0.23 × (surface ROS - critical ROS))   when surface ROS > critical ROS
   CFB = 0                                               otherwise

A fuel type with no crown fuel load (D-1, S-1…S-3, O-1) has ``CFB = 0``.

C6 crown fire
-------------

C6 uses a separate crown rate of spread:

.. code-block:: text

   FME = ((1.5 - 0.00275 × FMC)^4) / (460 + 25.9 × FMC) × 1000
   RSC = 60 × (1 - exp(-0.0497 × ISI)) × FME / 0.778

The head fire rate of spread is the surface ROS plus the crown fraction of the difference
between the crown ROS and the surface ROS.

Classification
--------------

The fire description is:

``S``
   Surface fire, ``CFB < 0.1``.
``I``
   Intermittent or passive crown fire, ``0.1 <= CFB < 0.9``.
``C``
   Active crown fire, ``CFB >= 0.9``.

When a canopy bulk density is supplied, the Van Wagner active-crown threshold is also
reported: the head fire ROS reaches ``3 / CBD`` m/min.

Validation
----------

The implementation is validated against the ``cffdrs`` R package:

- all 17 fuel types at FFMC 90, BUI 60, 10 km/h wind, flat ground;
- a 320-point grid across C2, C3, C7, M1, and S1;
- three C6 cases, including two active crown fires.

Crown fraction burned and head fire rate of spread match within 0.02; head fire intensity
matches within 1.0 kW/m. The fire description matches on every case.

Example
-------

.. code-block:: bash

   python examples/fire_crown_demo.py

The demo prints:

.. code-block:: text

   fuel  CFB    FD  surface ROS  head ROS  HFI kW/m  flame m
     C2  0.809  I        8.33      8.33     7845.4    4.80
     C4  0.765  I        8.79      8.79     7039.7    4.56
     M3  0.806  I       10.36     10.36     8444.5    4.96
   C6 crown case: FFMC 95, BUI 80, WS 20 -> CFB 0.962, C, HFI 45409.1 kW/m

Limits
------

- Flat ground only. Slope adjustment is P156.4.
- No spotting or ember transport.
- No growth geometry; the result is a point/weather behaviour, not a perimeter.
- The FMC is derived from latitude, longitude, elevation, and Julian day, or supplied
  explicitly.
- The active-crown threshold is optional because it needs a canopy bulk density; the FBP
  ``CFB`` class is always reported.
- The VRI-to-FBP fuel-type mapping is P156.9.

Cross-references
----------------

- :doc:`fire-fbp`
- :doc:`fire-behaviour`
- :doc:`fire-weather`
