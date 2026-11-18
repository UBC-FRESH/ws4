# TSA24 tile estate: growth fire through evaluation and optimization

This note closes the loop from the calibrated raster fire to an estate-scale process run, an
optimizer candidate, and a scenario risk aggregate. It is a pilot on a 30 km tile, not a full
TSA24 estate.

## Setup

The 30 km tile is the same real-layer tile used in the fire-regime pilot:

- 11,203 burnable 250 m cells
- real VRI fuel, crown closure, and conifer fraction
- real SRTM slope, aspect, and elevation
- VRI water-edge wetting

A 200-fragment subset (1,250 ha) around a real ignition was used for the estate run so the
optimizer could be exercised without a full-dataset compile. The subset uses one cohort per
fragment with `PL`, age 60, and 100 t/ha initial biomass. That fixed cohort is a substitute for
the VRI species and age attributes, which the saved raster layers do not carry.

The fire is the FBP growth engine on the full 30 km tile: one ignition, 240 minutes, constant
FFMC 93.8, BUI 108.2, wind 6.8 km/h at 270 degrees, with water-edge wetting. It reached 169
fragments (1,056.25 ha) on the full tile and 14 fragments (87.5 ha) inside the subset.

## Evaluation

A three-year schedule harvested ten blocks (62.5 ha) at offset 1 and ran the growth fire at
offset 0. The final accounts were:

| Account | Value |
| --- | ---: |
| `bridge.volume_m3` | 123,447.8 |
| `state.biomass_t` | 123,447.8 |
| `harvest.area_ha_total` | 62.5 |
| `fire.burned_area_ha_total` | 87.5 |
| `fire.count_total` | 14 |

## Optimizer

The same ten blocks formed a one-treatment, three-year schedule grammar. With the fixed growth
fire source and a target of at least 25 ha harvested, the hill-climb completed five rounds and
reached the target:

- best schedule: four block/offset entries
- `harvest.area_ha_total`: 25.0
- objective: 0.0
- `bridge.volume_m3`: 127,656.3
- `fire.burned_area_ha_total`: 87.5

The fire source therefore participates in the candidate evaluations rather than being applied
after optimization.

## Risk ensemble

Five scenarios varied the ignition cell and the weather state (FFMC 90.8-94.0, BUI 103-115,
wind 5.2-10.0 km/h) and ran the same three-year schedule. Each scenario built its own growth
fire source from the real layers.

| Scenario | Fire in subset (ha) | Final biomass (t) |
| --- | ---: | ---: |
| 1 | 31.2 | 129,760.5 |
| 2 | 6.2 | 132,566.1 |
| 3 | 68.8 | 126,954.9 |
| 4 | 68.8 | 126,954.9 |
| 5 | 168.8 | 118,538.0 |

The 90% lower-tail CVaR of final biomass was 118,538.0 t. The spread comes from the different
fire realizations and the stochastic process run.

## Boundary

The 200-fragment subset is not a compiled TSA24 estate. Species, age, and initial biomass are
fixed substitutes for VRI attributes. The optimizer run uses one fire realization and a simple
harvest target; the risk ensemble has five scenarios and no suppression model. The result
demonstrates the integration path, not a calibrated estate forecast.
