# TSA24 24-tile real-layer fire-regime calibration

This run expands the six-tile pilot to 24 real-layer tiles spread across the TSA24 block
extent. Each tile has a 30 km VRI/SRTM/water layer stack, historical perimeter sizes clipped to
the tile, and a 30-fire simulated ensemble with observed local durations and two-tier
suppression.

## Design

- 24 tiles, selected from the highest-density 30 km block bins with a 30 km separation
- real VRI fuel/crown, SRTM terrain, and water-edge wetting
- 30 simulated fires per tile, 720 total
- local 2023 daily FWI weather, 153 days per tile
- local incident durations where available
- 75% initial attack: 0.375-0.875 km ring, closed in 0-30 minutes
- 25% extended attack: 1.625-2.125 km ring, closed in 0-180 minutes
- no spotting

Historical perimeters cover 1950-2024.

## Aggregate size distribution

| Statistic | Historical | Simulated |
| --- | ---: | ---: |
| fires | 432 | 720 |
| mean | 512.9 ha | 129.9 ha |
| median | 23.0 ha | 56.3 ha |
| p90 | 490.2 ha | 619.4 ha |
| maximum | 25,114.8 ha | 856.3 ha |

The model misses both ends of the distribution:

- it overproduces moderate fires: median 56.3 ha instead of 23.0 ha
- it underproduces the extreme tail: maximum 856 ha instead of 25,115 ha
- the mean is therefore far too low, while p90 is too high
- the 25% extended-attack ring caps the simulated maximum

Several tiles contain historical fires above 5,000 ha, including a 25,115 ha event. No
simulated tile exceeds 856 ha.

Tile-level variation is large. Some tiles have only a few historical fires; one northern tile
has none. The aggregate is therefore more informative than any single tile.

## Interpretation

The current suppression mixture is too uniform. It needs:

- faster or smaller initial attack to lower the median
- rarer, larger escape fires that are not capped by the extended-attack ring
- a duration/weather tail that can produce multi-thousand-hectare events

The real fuel, terrain, and water layers are doing useful work; the remaining error is mainly
the suppression and escape representation.

## Boundary

The ensemble is not count-matched to the 432 historical fires. Weather is one fire season.
Historical perimeters are clipped to tile boundaries, and the 24 tiles are a stratified sample,
not the whole 5.9 M ha TSA24 area. The support map is not used in these per-tile runs.
