Fire weather and the FWI moisture codes
=======================================

Purpose
-------

The Canadian Forest Fire Weather Index (FWI) System turns daily weather into the moisture and
spread codes that the FBP surface-fire model consumes. This page specifies the daily weather
contract, the starting state, the seven FWI outputs, and the validation against the reference
implementation.

The codes are a weather/moisture layer, not a fire-behaviour model by themselves. The FBP
surface-fire equations are a later P151 task.

Daily weather
-------------

``DailyWeather`` carries:

- year, month, and day;
- dry-bulb temperature in degrees Celsius;
- relative humidity in percent;
- ten-metre wind speed in kilometres per hour;
- precipitation in millimetres;
- latitude in decimal degrees (default 55).

The month and latitude select the standard day-length adjustment for the Duff Moisture Code
and Drought Code. Relative humidity is clamped just below 100 percent inside the FFMC
calculation, matching the reference.

Starting state
--------------

``initial_fwi_state(ffmc=85, dmc=6, dc=15)`` returns the standard starting FFMC, DMC, and DC.
The derived indices are zero until the first step.

Outputs
-------

``FWIEngine.step(weather)`` returns an ``FWIState`` with:

``ffmc``
   Fine Fuel Moisture Code.
``dmc``
   Duff Moisture Code.
``dc``
   Drought Code.
``isi``
   Initial Spread Index.
``bui``
   Buildup Index.
``fwi``
   Fire Weather Index.
``dsr``
   Daily Severity Rating, ``0.0272 × FWI^1.77``.

``fwi_sequence(weather, initial)`` runs the engine over a daily sequence. The engine is
stateful: each day uses the previous day's FFMC, DMC, and DC.

Validation
----------

The implementation is tested against the ``cffdrs`` R package, the Canadian Forest Fire Danger
Rating System reference. The test fixtures are a ten-day sequence at latitude 55 and the same
sequence at latitude 20. All seven codes match within ``1e-4`` over the full sequence.

The reference package is a validation oracle only, not a runtime dependency.

Example
-------

.. code-block:: bash

   python examples/fire_fwi_demo.py

The demo prints:

.. code-block:: text

   day  FFMC    DMC     DC     ISI    BUI    FWI    DSR
     1   88.23    8.97   22.30   5.50   8.97   5.62  0.578
     3   77.78   12.87   36.91   1.38  13.75   1.00  0.027
     7   61.58   17.72   61.74   0.58  20.63   0.53  0.009
    10   91.67   29.76   85.99  11.00  31.91  19.02  4.997

Programmatically:

.. code-block:: python

   from ws4.fire import DailyWeather, fwi_sequence, initial_fwi_state

   weather = [DailyWeather(2026, 7, 1, 20, 40, 10, 0, 55)]
   state = fwi_sequence(weather, initial_fwi_state())[0]
   print(state.ffmc, state.bui, state.fwi)

Limits
------

- The FBP fuel types and surface-fire equations are not implemented yet; they are split to
  P151.8.
- The weather is daily, not hourly or diurnal.
- The latitude adjustment is the standard Canadian form; it is not a site-specific
  day-length model.
- The FWI codes are not a fire-behaviour prediction. They become useful when the FBP
  surface-fire equations consume them.

Cross-references
----------------

- :doc:`fire-behaviour`
- :doc:`ecosystem-fire`
- :doc:`ecosystem-scenarios`
