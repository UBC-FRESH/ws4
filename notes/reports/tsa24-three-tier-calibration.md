# TSA24 three-tier suppression calibration

The 24-tile baseline used two containment tiers and could not produce fires above 856 ha.
This sweep tested three tiers: fast initial attack, medium containment, and an uncapped escape
fraction.

## Historical target

The 432 historical perimeters in the 24 tiles have:

| Statistic | Historical |
| --- | ---: |
| median | 23.0 ha |
| p90 | 490.2 ha |
| over 100 ha | 26.2% |
| over 500 ha | 10.0% |
| over 1,000 ha | 7.9% |
| over 5,000 ha | 3.0% |
| maximum | 25,114.8 ha |

All runs used 30 fires per tile, 720 total, with the real VRI/SRTM/water layers and local 2023
FWI weather. The probabilities are `(initial, medium, escape)`.

## Sweep

| Initial | Initial ring | Medium | Medium ring | Escape | Median | p90 | >100 | >500 | >1,000 | >5,000 | Max |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| .72 | 0.75-2.5 | .20 | 3-5.5 | .08 | 6.3 | 6.3 | 5.1% | 1.4% | 1.3% | 1.0% | 17,944 |
| .60 | 1.5-3.5 | .30 | 3-6 | .10 | 6.3 | 56.3 | 6.5% | 1.9% | 1.9% | 0.4% | 16,138 |
| .55 | 2-3.5 | .33 | 4-7 | .12 | 12.5 | 81.3 | 9.3% | 2.2% | 2.1% | 0.4% | 16,138 |
| .55 | 1.5-3.5 | .30 | 4-8 | .15 | 12.5 | 82.5 | 9.7% | 2.6% | 2.1% | 0.4% | 16,138 |
| .50 | 2-4 | .30 | 4-8 | .20 | 43.8 | 490.6 | 17.4% | 10.0% | 9.7% | 5.6% | 36,531 |
| .55 | 2-4 | .25 | 4-8 | .20 | 43.8 | 490.6 | 16.4% | 10.0% | 9.7% | 5.6% | 36,531 |

The last two rows match p90 and the over-500 fraction, but their median is too high and their
tail is too heavy. The rows above them have better medians but far too few medium and large
fires.

## Finding

Discrete containment tiers produce a bimodal distribution: fires either stop small or escape
to thousands of hectares. The historical distribution is smoother. Matching it requires a
continuous initial-attack radius or containment-time distribution, with escape probability
conditioned on fuel, weather, and duration. Adding more fixed tiers is not the right fix.

## Boundary

The sweep uses the same 720-fire sample and weather as the baseline. It is a structural
diagnostic, not a calibrated suppression model.
