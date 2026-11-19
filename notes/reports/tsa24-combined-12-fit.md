# TSA24 combined-12 containment fit

The held-out result showed that fitting six calibration tiles overfits the tail. This run used
the combined first 12 tiles as the training set and tested two containment structures.

## Combined-12 historical target

| Statistic | Historical |
| --- | ---: |
| fires | 204 |
| median | 21.7 ha |
| p90 | 267.0 ha |
| over 500 ha | 6.9% |
| over 1,000 ha | 4.4% |
| maximum | 11,394.6 ha |

Each candidate used 10 fires per tile, 120 fires total, with fire-danger-weighted weather at
50 m.

## Candidate A: moderate target, small escape

- containment target: 45 ha median, 0.80 log-sigma
- 1% uncapped escape
- target above 3,000 ha treated as escape

| Statistic | Historical | Candidate A |
| --- | ---: | ---: |
| median | 21.7 ha | 31.9 ha |
| p90 | 267.0 ha | 616.6 ha |
| over 500 ha | 6.9% | 13.3% |
| over 1,000 ha | 4.4% | 9.2% |
| maximum | 11,394.6 ha | 25,296.8 ha |

The tail is still too heavy, and the median is too high.

## Candidate B: heavy-tailed target, almost no escape

- containment target: 35 ha median, 1.80 log-sigma
- 0.5% uncapped escape
- target above 10,000 ha treated as escape

| Statistic | Historical | Candidate B |
| --- | ---: | ---: |
| median | 21.7 ha | 26.6 ha |
| p90 | 267.0 ha | 140.3 ha |
| over 500 ha | 6.9% | 0.0% |
| over 1,000 ha | 4.4% | 0.0% |
| maximum | 11,394.6 ha | 160.3 ha |

The heavy-tailed containment target does not produce large fires because the ring is never
reached within the sampled duration/weather. The tail collapses.

## Finding

Neither candidate matches the combined historical distribution:

- with escape, the tail is too heavy
- with a heavy-tailed containment target and almost no escape, the tail disappears

Containment area, duration, weather, and escape cannot be tuned independently. The model needs
an escape/growth mechanism that is conditioned on fire weather and duration, rather than a fixed
probability or a target-area tail.

Held-out validation is deferred because the training fit failed.

## Boundary

Twelve training tiles, 10 fires each, 50 m cells upsampled from 250 m layers, one fire season
of weather weights. This is a structural diagnostic, not a calibrated regime.
