# Credible fire behaviour and growth

Status: active (P151)
Phase: P151 (Credible fire behaviour and growth)
Date: 2026-11-08
Related: `docs/reference/fire-behaviour.rst`, `docs/reference/ecosystem-fire.rst`,
`notes/design/ws4-stochastic-landscape.md`, parent issue #890

## 1. Why Rothermel first

The P144 fire process uses a graph-percolation probability. It is useful for the event, tape,
package, and scene plumbing, but it is not a fire-behaviour model. The first credibility step
is a surface-fire kernel that a fire modeller can inspect and compare: Rothermel (1972) with the
standard corrections.

The kernel is deliberately separate from growth. The kernel answers "how fast does the head
fire spread under this fuel, moisture, wind, and slope?" The growth engine, later, answers
"where is the perimeter over time?" Keeping them separate makes the validation honest.

## 2. Contracts

The metric units are part of the contract:

- fuel load: tonnes per hectare;
- surface-to-volume ratio: square metres per cubic metre;
- heat content: kilojoules per kilogram;
- fuel bed depth: centimetres;
- moisture: percent of dry weight;
- midflame wind: kilometres per hour;
- slope: percent.

`FuelModel` holds the five fuel classes, the depth, the moisture of extinction, and the static
or dynamic model type. `FuelMoisture` holds the five class moistures. `FireEnvironment` holds
wind and slope, with optional provenance for direction, aspect, elevation, temperature, and
relative humidity.

The 13 Anderson models and the 16 Scott-Burgan moisture scenarios are included. The parameters
are public scientific data; the implementation is original.

## 3. Kernel and corrections

The Python kernel follows the Rothermel formulation and the standard corrections used by
modern implementations:

- Frandsen's effective heating number;
- Albini's wind and slope adjustments;
- the Andrews et al. (2013) wind-limit treatment as implemented by the reference;
- the dynamic live-herb transfer for dynamic models.

The internal calculation follows the model's imperial formulation and converts the inputs and
outputs to metric. The result object carries every intermediate value needed to audit a run:
reaction intensity, wind and slope factors, heat source and sink, packing ratios, characteristic
SAV and bulk density, and the live moisture of extinction.

Head fire intensity and flame length are derived for the account and visual layers, with an
explicit heat yield and consumption fraction. They are not part of the Rothermel
standard-case validation.

## 4. Validation

The first oracle is the R `Rothermel` package (Vacchiano and Ascoli, 2015), used only to
generate reference values. The package implements the published model and its corrections.

The tests compare:

- all 13 Anderson models at the `D2L2` moisture scenario, 8 km/h wind, and level ground;
- the custom dynamic example from the reference documentation;
- a 15-point wind/slope grid for A3.

The rate of spread, reaction intensity, wind factor, heat source, and heat sink match within
0.01 in the reported units. The tests also cover monotonicity in wind, slope, and moisture, and
the extinction case where the dead moisture exceeds the moisture of extinction.

The standard-case pass is necessary, not sufficient. The next validation layers are a public
fire-growth model and an observed perimeter.

## 5. FBP surface fire

P151.7 added the Canadian FWI moisture codes. P151.8 added the FBP surface-fire layer:

- the 17 standard FBP fuel types;
- surface fuel consumption, the buildup effect, and the surface rate of spread;
- the surface head fire intensity, `300 x SFC x ROS`, and a derived flame length;
- the M1/M2 and M3/M4 blends and the O1 crown-closure/grass-load parameters.

The FBP surface results match the `cffdrs` reference within 0.02 on all 17 fuel types at
FFMC 90, BUI 60, 10 km/h, flat ground, and on a 320-point grid across C2, C3, C7, M1, and S1.
The C6 surface component is validated separately. The layer is flat-ground and surface-only:
slope adjustment is P151.4, and crown fire is P151.3.

## 6. What follows

- **P151.3 Crown fire.** Van Wagner initiation, Cruz et al. propagation, and the passive to
  active transition.
- **P151.3 Crown fire.** Van Wagner initiation, Cruz et al. propagation, and the passive to
  active transition.
- **P151.4 Growth.** A site/fuel grid, slope adjustment, and an elliptical or cellular growth
  engine, with homogeneous shape tests and a barrier test.
- **P151.5 Integration.** The P144 event record carries the fuel, weather, slope, kernel
  version, ROS, intensity, and flame length. The P150 viewer's flames and smoke scale with
  those values.
- **P151.6 Benchmark.** A public growth-model comparison and an observed-fire case, with the
  tolerances and limits named.

## 7. Limits and risks

- A standard-case pass does not prove a landscape fire. The growth and benchmark tasks are
  separate.
- The derived intensity and flame length depend on the heat yield and consumption fraction;
  those are scene parameters and must be visible in the event record.
- The FBP fuel types and moisture codes are not implemented yet. Mapping them to Rothermel
  proxies would be a modelling choice, not a validation.
- The 13 Anderson models are a validation set, not a BC fuel map. The VRI/Nemora fuel layer
  must be built and documented separately.
- Unit conversion is the main silent-error risk; the tests pin the reference values in the
  metric contract.

## 8. References

- Rothermel, R. C. (1972). A mathematical model for predicting fire spread in wildland fuels.
- Albini, F. A. (1976). Computer-based models of wildland fire behavior.
- Andrews, P. L., Cruz, M. G., and Rothermel, R. C. (2013). Examination of the wind speed limit
  function in the Rothermel surface fire spread model.
- Scott, J. H., and Burgan, R. E. (2005). Standard fire behavior fuel models.
- Vacchiano, G., and Ascoli, D. (2015). An implementation of the Rothermel fire spread model in
  the R programming language. Used as a validation oracle only.
