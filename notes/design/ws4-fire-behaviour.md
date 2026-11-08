# Credible fire behaviour and growth

Status: active (P154)
Phase: P154 (Credible fire behaviour and growth)
Date: 2026-11-08
Related: `docs/reference/fire-behaviour.rst`, `docs/reference/fire-growth.rst`,
`docs/reference/ecosystem-fire.rst`, `notes/design/ws4-stochastic-landscape.md`,
parent issue #890

## 1. Why Rothermel first

The P144 fire process uses a graph-percolation probability. It is useful for the event, tape,
package, and scene plumbing, but it is not a fire-behaviour model. The first credibility step
is a surface-fire kernel that a fire modeller can inspect and compare: Rothermel (1972) with the
standard corrections.

The kernel is deliberately separate from growth. The kernel answers "how fast does the head
fire spread under this fuel, moisture, wind, and slope?" The P154.4 growth engine answers
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

P154.7 added the Canadian FWI moisture codes. P154.8 added the FBP surface-fire layer:

- the 17 standard FBP fuel types;
- surface fuel consumption, the buildup effect, and the surface rate of spread;
- the surface head fire intensity, `300 x SFC x ROS`, and a derived flame length;
- the M1/M2 and M3/M4 blends and the O1 crown-closure/grass-load parameters.

The FBP surface results match the `cffdrs` reference within 0.02 on all 17 fuel types at
FFMC 90, BUI 60, 10 km/h, flat ground, and on a 320-point grid across C2, C3, C7, M1, and S1.
The C6 surface component is validated separately. The layer is flat-ground and surface-only:
slope adjustment is P154.4, and crown fire is P154.3.

## 6. Crown fire

P154.3 added the Van Wagner initiation threshold, the FBP crown fraction burned, the C6
crown rate of spread and head-fire blend, the S/I/C fire description, and an optional Van
Wagner active-crown threshold. CFB and ROS match `cffdrs` within 0.02, HFI within 1.0 kW/m,
and the fire description exactly on the 17-fuel-type base table, a 320-point grid, and three
C6 cases.

## 7. Growth and perimeter

P154.4 added `ws4/fire/growth.py`:

- `SiteGrid` carries the fuel type, the cell geometry, FFMC, BUI, wind, slope and aspect, the
  optional M/O parameters, and a burnable mask.
- `effective_wind` folds slope into the wind vector using the FBP slope adjustment: the
  zero-wind surface rate of spread, the slope factor, the inverse RSI relation, the effective
  ISI, and the effective wind speed, then a vector addition. It matches `cffdrs` on 40
  wind/slope/fuel cases within 0.02 km/h and 0.1 degree.
- `grow_fire` uses a minimum-travel-time / Huygens construction. The head rate of spread comes
  from the validated FBP surface and crown layer, the length-to-breadth ratio comes from the
  FBP ellipse relation, and each neighbour receives an arrival time from the directional ROS.
  A priority queue keeps the earliest arrival per cell.
- Snapshots record time, burned cells, area, and exposed perimeter. Non-burnable cells never
  ignite, so a barrier is a mask.
- `fragment_ignition_times` and `fragment_ignition_events` map the front to P144 fragment
  ignition events. Each event carries the minimum cell ignition time, the burned fragment
  area, and the growth inputs and outputs as attributes. Growth minutes become fractional
  years on the event clock.

The shape tests cover a circle with no wind or slope, a downwind ellipse, an upslope
displacement, a combined wind/slope vector, a non-burnable barrier, and monotone snapshots.
The flat-ground wind ellipse matches the analytic length and width within 10 percent. C6 slope
adjustment is explicitly unsupported and raises; flat-ground C6 growth is supported.

## 8. What follows

- **P154.5 Integration.** The P144 event record carries the fuel, weather, slope, kernel
  version, ROS, intensity, and flame length. The P155 viewer's flames and smoke scale with
  those values. The growth front maps to fragment ignition times.
- **P154.6 Benchmark.** A public growth-model comparison and an observed-fire case, with the
  tolerances and limits named.
- **P154.9 VRI mapping.** Map VRI species, age, and canopy attributes to FBP fuel types, with
  an accuracy report and an explicit unknown class.
- **P155 3D scene.** Renumber the 3D fire scene phase from the old P150 label. `main` now
  carries P150 (GPU guard), P151 (web console), P152 (sandboxed runner), and P153 (assistant
  script review), so the 3D scene is P155.

## 9. Limits and risks

- A standard-case pass does not prove a landscape fire. The growth and benchmark tasks are
  separate.
- The derived intensity and flame length depend on the heat yield and consumption fraction;
  those are scene parameters and must be visible in the event record.
- The growth grid is homogeneous in fuel and weather; heterogeneous fuel and the fragment
  event-log bridge are P154.5 and later.
- The growth perimeter is the raster cell-edge length, not a sub-cell contour. The circle
  perimeter is about 16 percent above the analytic circle on the test grid.
- C6 slope adjustment is unsupported; the engine raises rather than silently substituting a
  surface proxy.
- The 13 Anderson models are a validation set, not a BC fuel map. The VRI/Nemora fuel layer
  must be built and documented separately.
- Unit conversion is the main silent-error risk; the tests pin the reference values in the
  metric contract.

## 10. References

- Rothermel, R. C. (1972). A mathematical model for predicting fire spread in wildland fuels.
- Albini, F. A. (1976). Computer-based models of wildland fire behavior.
- Andrews, P. L., Cruz, M. G., and Rothermel, R. C. (2013). Examination of the wind speed limit
  function in the Rothermel surface fire spread model.
- Scott, J. H., and Burgan, R. E. (2005). Standard fire behavior fuel models.
- Van Wagner, C. E. (1977). Conditions for the start and spread of crown fire.
- Cruz, M. G., Alexander, M. E., and Wakimoto, R. H. (2005). Development and evaluation of a
  crown fire spread model.
- Forestry Canada Fire Danger Group (1992). Development and structure of the Canadian Forest
  Fire Behavior Prediction System.
- Vacchiano, G., and Ascoli, D. (2015). An implementation of the Rothermel fire spread model in
  the R programming language. Used as a validation oracle only.
- Wang, X., Wotton, B. M., Cantin, A. S., et al. The Canadian Forest Fire Danger Rating System
  and `cffdrs`. Used as a validation oracle only.
