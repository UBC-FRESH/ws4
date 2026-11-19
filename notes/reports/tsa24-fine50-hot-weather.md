# TSA24 50 m hot-weather diagnostic

The 50 m subset under randomly sampled daily weather produced a one-cell median. This test
separated weather from resolution by rerunning the same six tiles and 50 m grid under a
consistently hot state: 30 C, 25% relative humidity, 8 km/h wind, no rain.

The FWI sequence reached FFMC 93.8, BUI 11-60, and FWI 10.5-26.2 over ten days.

## Result

| Statistic | Historical | Hot 50 m |
| --- | ---: | ---: |
| fires | 87 | 120 |
| mean | 221.1 ha | 2,392.4 ha |
| median | 15.6 ha | 11.3 ha |
| p90 | 229.0 ha | 1,078.7 ha |
| p95 | 555.1 ha | 25,352.4 ha |
| maximum | 10,602.2 ha | 46,788.8 ha |
| over 100 ha | 23.0% | 25.8% |
| over 500 ha | 5.7% | 15.0% |
| over 1,000 ha | 3.4% | 10.8% |

The hot weather brings the median close to the historical value, but the tail is far too
heavy. Attempts to narrow the containment distribution did not remove the tail reliably; the
run became unstable across tiles.

## Finding

Random daily weather was suppressing most fires to one cell. Fire-weather conditioning matters
as much as containment. But hot weather alone overproduces large fires, so the calibration
still needs:

- observed fire-weather weighting or actual fire-date weather
- a containment perimeter that controls the tail without collapsing the median
- a duration/escape relation that is not a fixed probability

## Boundary

Six tiles, 20 fires per tile, 50 m cells upsampled from 250 m VRI/SRTM data. The hot state is a
diagnostic, not observed fire weather.
