# TSA24 tail-fire audit

The 24-tile calibration could not produce the historical fires above 5,000 ha. This audit
checked those fires individually.

## Tail events

Thirteen historical fires above 5,000 ha were found in the 24 tiles. For each event, the real
tile layers were used with a 10-hour active day and 90 days of antecedent weather to initialize
the FWI system.

| Tile | Fire | Year | Observed ha | Potential ha | Active days | FWI |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| t05 | G00300 | 1961 | 11,394.6 | 24,018.8 | 3 | 27.2 |
| t04 | G20069 | 1985 | 6,457.6 | 25,643.8 | 2 | 24.0 |
| t22 | C10480 | 2009 | 6,618.2 | 24,575.0 | 8 | 24.3 |
| t19 | G40151 | 2010 | 6,097.0 | 9,537.5 | 6 | 14.8 |
| t22 | G40198 | 2014 | 15,255.1 | 8,300.0 | 8 | 5.7 |
| t13 | G10037 | 2015 | 25,114.8 | 30,350.0 | 8 | 7.6 |
| t22 | C10784 | 2017 | 15,069.3 | 27,006.3 | 8 | 43.9 |
| t16 | G40837 | 2017 | 6,722.2 | 6.3 | 1 | 7.6 |
| t16 | G41607 | 2018 | 14,260.2 | 693.8 | 2 | 18.0 |
| t07 | G51632 | 2018 | 10,602.2 | 14,043.8 | 2 | 23.9 |
| t17 | R11498 | 2018 | 11,648.3 | 16,362.5 | 5 | 22.1 |
| t16 | G41269 | 2021 | 9,573.7 | 3,456.3 | 1 | 29.7 |
| t16 | G41307 | 2023 | 11,416.7 | 3,918.8 | 8 | 15.9 |

## Finding

Without antecedent weather, the event-day FWI initialization produced low BUI and most fires
failed to reach their observed size. With 90 days of spin-up, 8 of the 13 events have potential
at least as large as the observed fire. The tail is therefore not fundamentally absent from the
growth model.

Five events still fail. They are concentrated in t16 and in years/events where the active window
was short or the local weather was milder. This points to local ignition/timing and weather
reconstruction, not a missing global tail process.

The previous potential sample, which used only event-day weather, systematically underestimated
the tail. Potential-growth calibration must use antecedent FWI spin-up.

## Boundary

The audit uses one reconstructed weather series per fire and assumes the perimeter date is the
ignition date. The active window is inferred from daily rain. This is a diagnostic, not a
calibrated event reconstruction.
