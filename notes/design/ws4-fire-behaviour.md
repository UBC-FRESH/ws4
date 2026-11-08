# Credible fire behaviour and growth

Status: active (P156)
Phase: P156 (Credible fire behaviour and growth)
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
fire spread under this fuel, moisture, wind, and slope?" The P156.4 growth engine answers
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

P156.7 added the Canadian FWI moisture codes. P156.8 added the FBP surface-fire layer:

- the 17 standard FBP fuel types;
- surface fuel consumption, the buildup effect, and the surface rate of spread;
- the surface head fire intensity, `300 x SFC x ROS`, and a derived flame length;
- the M1/M2 and M3/M4 blends and the O1 crown-closure/grass-load parameters.

The FBP surface results match the `cffdrs` reference within 0.02 on all 17 fuel types at
FFMC 90, BUI 60, 10 km/h, flat ground, and on a 320-point grid across C2, C3, C7, M1, and S1.
The C6 surface component is validated separately. The layer is flat-ground and surface-only:
slope adjustment is P156.4, and crown fire is P156.3.

## 6. Crown fire

P156.3 added the Van Wagner initiation threshold, the FBP crown fraction burned, the C6
crown rate of spread and head-fire blend, the S/I/C fire description, and an optional Van
Wagner active-crown threshold. CFB and ROS match `cffdrs` within 0.02, HFI within 1.0 kW/m,
and the fire description exactly on the 17-fuel-type base table, a 320-point grid, and three
C6 cases.

## 7. Growth and perimeter

P156.4 added `ws4/fire/growth.py`:

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

## 8. VRI mapping

P156.9 added `ws4/fire/vri.py`. A `VriStand` carries the leading species, conifer and
deciduous fractions, crown closure, age, height, land cover, optional explicit fuel type,
and treatment. `map_vri_stand` applies a deterministic, ordered rule set and returns an
`FbpFuelAssignment` with the canonical FBP type, rule id, mapping version, confidence,
source fields, and notes. `map_vri_table` returns one provenance row per stand.

The rules cover explicit FBP types, non-fuel land cover, grass and slash, sparse cover,
deciduous, mixedwood, pine by age, Douglas-fir, larch, and spruce/fir by crown closure.
Unknown species, unknown land cover, and an unlabelled forest stand raise `VriError` rather
than inventing a type. The mapping is a modelling decision, not a measurement, and the
fixture is representative rather than a copy of a private VRI inventory.

## 9. Observed fire validation

P157.1 adds `ws4/fire/observed.py` and the Dogrib (RWF085) fixture. The contract records the
Prometheus source, archive, custom NAD83 Transverse Mercator, 100 m grid, local event window,
ignition point, hourly weather, FBP fuel grid, elevation grid, and observed perimeters. The
loader validates grid agreement, fuel lookup coverage, hourly weather continuity, event-window
coverage, ignition containment, and perimeter overlap. The fixture has a 935 ha start perimeter
and a 10,223 ha final perimeter across 25 polygons, including spot fires. The comparison
harness and metrics are P157.2.

## 10. What follows

- **P156.5 Integration.** Done for the event log and accounts. `FireBehaviourConfig` selects
  the FBP kernel; every behaviour-driven fire event carries the fuel, weather, slope,
  effective wind, kernel version, ROS, intensity, flame length, crown fraction, fuel
  consumption, and smoke strength. Accounts summarize ROS, intensity, flame length, and the
  area-weighted crown fraction. The P155 viewer reads the same attributes when its event
  coupling lands; the scene package stays on the P155 branch, not here.
- **P157.2 Observed comparison.** Compare the P156 growth engine with the Dogrib perimeters
  using area, perimeter, centroid, IoU, Sorensen, and orientation, with named tolerances.
- **P156.9 VRI mapping.** Done: the VRI stand contract, deterministic rules, explicit
  non-fuel and unknown paths, and provenance are in `ws4/fire/vri.py`.
- **P155 3D scene.** Renumbered from the old P150 label and now on
  `feature/p155-fire-3d`. `main` carries P150 (GPU guard), P151 (web console), P152
  (sandboxed runner), P153 (assistant script review), and P154 (TSA 29 GPU stock).

## 11. Limits and risks

- A standard-case pass does not prove a landscape fire. The growth and benchmark tasks are
  separate.
- The derived intensity and flame length depend on the heat yield and consumption fraction;
  those are scene parameters and must be visible in the event record.
- The growth grid is homogeneous in fuel and weather; heterogeneous fuel is a later task. The
  event log and accounts carry the kernel outputs; the P155 viewer coupling is separate.
- The growth perimeter is the raster cell-edge length, not a sub-cell contour. The circle
  perimeter is about 16 percent above the analytic circle on the test grid.
- C6 slope adjustment is unsupported; the engine raises rather than silently substituting a
  surface proxy.
- The 13 Anderson models are a validation set, not a BC fuel map. The VRI-to-FBP rule set is
  documented and explicit, but it is not a regional calibration; Nemora tree synthesis remains
  P155.
- Unit conversion is the main silent-error risk; the tests pin the reference values in the
  metric contract.
- The Dogrib source licence is not explicit in the archive. The fixture is used for
  validation with attribution. Its weather and perimeter times are local time; no
  daylight-saving conversion is applied.
- The observed fire includes spot fires; the P156 growth engine does not model spotting. The
  comparison must report that mismatch.

## 12. References

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
