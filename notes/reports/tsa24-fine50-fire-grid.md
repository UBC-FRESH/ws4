# TSA24 50 m fire-grid calibration subset

The 250 m calibration could not represent the historical median because one burned cell is
6.25 ha and the next ring is about 50 ha. This test reran six real-layer tiles on a 50 m fire
grid to see whether resolution alone fixes the median.

## Design

- six tiles: central-west, south-east, far-east, north-west, far-north, central-east
- 20 fires per tile, 120 total
- 50 m fire cells, upsampled from the 250 m VRI/SRTM layers
- same continuous containment model as the 250 m test
- local 2023 FWI weather
- 87 historical perimeters in the same six tiles

## Result

| Statistic | Historical | 50 m simulated |
| --- | ---: | ---: |
| fires | 87 | 120 |
| mean | 221.1 ha | 906.2 ha |
| median | 15.6 ha | 0.25 ha |
| p90 | 229.0 ha | 133.7 ha |
| p95 | 555.1 ha | 5,169.6 ha |
| maximum | 10,602.2 ha | 22,489.5 ha |
| over 100 ha | 23.0% | 10.8% |
| over 500 ha | 5.7% | 7.5% |
| over 1,000 ha | 3.4% | 7.5% |

The median is still wrong: it now sits at the 50 m one-cell floor of 0.25 ha. The simulation
is strongly bimodal: most fires stop in one cell, a small number escape to thousands of
hectares.

## Finding

The 250 m resolution was part of the problem, but not the whole problem. The containment-ring
construction is collapsing interior growth: placing a closed ring at the target radius does not
guarantee that the interior burns to that area. Refining the grid only lowers the floor.

The containment model needs to represent a **contained area or perimeter**, not just a ring
whose closure can stop the front before the interior fills. It also needs the interior fuel,
weather, and duration to determine how much of that area burns.

## Boundary

The 50 m layers are upsampled from 250 m VRI/SRTM data; this is a resolution test, not a true
50 m inventory. Six tiles and 120 fires are a subset. It is a structural diagnostic, not a
calibrated regime.
