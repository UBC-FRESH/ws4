# TSA24 relative-suppression fit and held-out validation

The relative model was fitted on the fixed potential-size sample from the first 12 tiles. The
same parameters were then applied unchanged to the remaining 12 tiles.

## Potential growth

At 250 m, active-spread potential growth is much larger than observed fires:

- median potential: about 70,000 ha
- p90 potential: about 85,700 ha
- maximum potential: about 87,000 ha

This is why suppression must retain a very small fraction of potential.

## Fitted parameters

The best global fit from the fixed-potential search:

- contained retained fraction: `0.000389` median, `1.281` log-sigma
- escaped retained fraction: `0.1078` median, `0.285` log-sigma
- escape cap: `12,000 ha`
- escape hazard intercept: `-4.409`
- duration/FWI/BUI/wind weights: `0.5`, `0.2`, `0.1`, `0.1`

## Training fit

Best-search training statistics:

| Statistic | Historical, first 12 | Fitted |
| --- | ---: | ---: |
| median | 21.7 ha | 22.4 ha |
| p90 | 267.0 ha | 203.5 ha |
| over 100 ha | 21.6% | 19.6% |
| over 500 ha | 6.9% | 5.4% |
| over 1,000 ha | 4.4% | 4.6% |
| maximum | 11,394.6 ha | 12,000.0 ha |

## Held-out validation

Applying the same parameters to the remaining 12 tiles:

| Statistic | Historical, last 12 | Validation |
| --- | ---: | ---: |
| median | 27.9 ha | 17.9 ha |
| p90 | 1,266.2 ha | 126.5 ha |
| p95 | 3,309.8 ha | 187.1 ha |
| maximum | 25,114.8 ha | 11,424.7 ha |
| over 100 ha | 30.3% | 13.3% |
| over 500 ha | 12.7% | 2.9% |
| over 1,000 ha | 11.0% | 2.9% |
| over 5,000 ha | 4.4% | 1.7% |

The fitted parameters underproduce the held-out tail by roughly a factor of ten at p90 and by
a factor of four in the over-500 fraction.

## Finding

The relative mechanism is correct in structure, but a single global fraction does not transfer
across the TSA24 tiles. The first 12 tiles are not representative of the last 12: the validation
tiles contain a much heavier historical tail.

A global two-parameter fraction is insufficient. The next fit needs spatial covariates — fuel,
terrain, active-spread duration, and region — or a hierarchical calibration by tile.

## Boundary

The potential sample is 20 fires per tile at 250 m. The historical comparison clips perimeters
to tiles. This is a calibration diagnostic, not a final regime.
