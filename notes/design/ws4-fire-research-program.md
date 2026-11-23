# WS4 fire-regime research program

Status: serious-science plan; supersedes the four manuscript drafts as a submission plan

Date: 2026-11-23

## Honest starting point

The current four drafts are not publication-grade. They demonstrate an open implementation and a
negative transfer result, but they do not yet contain the independent evidence a serious fire-science
or forest-management paper needs:

- the regional suppression map is in-sample;
- independent tile transfer is negative;
- the five-year estate case and sharded optimizer are demonstrations, not validated forecasts;
- the optimizer objective is harvest-only, so the “fire-aware” label is not earned;
- the external benchmark is one Dogrib fire, not a TSA24 validation;
- the support map and 24 named calibration layers are frozen derived inputs, not yet regenerated
  from raw block geometry.

The plan below is designed to produce either a defensible paper or a defensible negative result. It
does not assume the model will succeed.

## Shared principles

1. **Pre-register the test before running it.** Split, metrics, tolerances, and stopping rules are
   fixed in a protocol file.
2. **Separate calibration from validation.** In-sample residuals are never presented as skill.
3. **Use independent data.** Spatial holdout, temporal holdout, and observed fire perimeters are
   separate tests.
4. **Benchmark against an independent model.** FSim, BurnP3+, FireSTARR, or Cell2Fire on a shared
   landscape; document input differences.
5. **Propagate uncertainty.** Seeds, parameter uncertainty, weather, and observation error.
6. **Report failures.** A failed validation is a result, not a reason to retune on the test set.
7. **Keep the whole path reproducible.** Raw source → materialization → potential sample →
   calibration → validation → cases; no hidden local state.

## Paper 1: independent validation of the open TSA24 fire regime

**Working title:** *Can an open, reduced-form fire regime reproduce independent TSA24 fires? A
pre-registered spatial and temporal validation*

**Target:** *International Journal of Wildland Fire*; backup *Fire*.

**Core question:** Does the calibrated FBP growth + suppression/escape model reproduce independent
fire sizes and spatial perimeters in TSA24, and where does it fail?

**Hypotheses:**

- H1: The regional map reproduces the central fire-size distribution in held-out years better than
  the global fit.
- H2: Spatial transfer across tiles is weaker than temporal transfer within tiles.
- H3: The upper tail is underproduced because the escape-size realization, not the contained
  fraction, is misspecified.
- H4: A hierarchical model with suppression-capacity covariates improves transfer over independent
  per-tile fits.

**Needed data:**

- historical BC Wildfire perimeters with geometry, year, ignition date, and final size;
- hourly weather for each selected event and antecedent 90 days;
- observed start perimeter where available;
- VRI/SRTM/water layers;
- independent spatial and temporal splits fixed before fitting.

**Experiments:**

1. **Temporal holdout:** calibrate on fires before a fixed year, validate after it.
2. **Spatial holdout:** leave-tile-out and leave-region-out, with no test-tile tuning.
3. **Event-level spatial validation:** simulate selected observed fires from ignition/start
   perimeter and hourly weather; compare area, perimeter, centroid, IoU, Sorensen, orientation.
4. **External benchmark:** FSim, BurnP3+, FireSTARR, or Cell2Fire on a shared event/landscape.
5. **Uncertainty:** bootstrap potential sample, parameter posterior, weather ensemble, observation
   error; report intervals, not point ranks.
6. **Ablation:** global vs independent regional vs hierarchical; contained-only vs escape; cap
   sensitivity; tail-event model.

**Primary metrics:** median, p90, p95, over-1,000 ha, maximum, spatial IoU/Sorensen, centroid error,
area bias, interval coverage.

**Go/no-go:** the paper is publishable as a validation if the protocol is followed and the result is
reported, whether positive or negative. No model claim is made beyond the tested domain.

## Paper 2: fire-aware forest estate optimization

**Working title:** *Does process-based fire risk change optimal forest estate schedules? A
near-global comparison under uncertainty*

**Target:** *Canadian Journal of Forest Research*; backup *Forest Ecology and Management* or
*Environmental Modelling & Software*.

**Core question:** How do process-based fire risk and suppression assumptions change optimal harvest
schedules, volume, and tail risk relative to fire-blind and burn-probability planning?

**Current blocker:** the sharded objective is harvest-only; a fire-blind repeat produces the same
schedule. The paper cannot claim fire-aware optimization until the objective includes fire risk and
the solution is compared with a near-global baseline.

**Needed work:**

- add a local risk target or penalty (burned area, volume-loss CVaR, or a fire-sensitive harvest
  rule);
- build a global/near-global optimization on a reduced estate (e.g., 10–20 tiles) or a coordinated
  decomposition with quality bounds;
- compare fire-blind, burn-probability overlay, and process-based fire-aware schedules under multiple
  seeds;
- report volume, NPV/flow, burned area, CVaR, biomass/carbon side effects, runtime, and solution
  quality.

**Go/no-go:** no paper until the fire-aware objective changes the schedule or the null result is
demonstrated against a near-global baseline.

## Paper 3: open TSA24 fire-regime benchmark and data descriptor

**Working title:** *A reproducible TSA24 open fire-regime benchmark: source catalogue, layer
materialization, calibration, and validation cases*

**Target:** *Data in Brief*; backup *Scientific Data* or *Fire* data descriptor.

**Contribution:** a citable, versioned data/software package with raw source resolution, layer
materialization, support map, potential sample, calibration, validation, and compact results.

**Required before submission:**

- derive the support map from block geometry, not a frozen NPZ;
- regenerate the 24 named calibration layers from raw;
- one-command pipeline from raw sources to results;
- DOI, licence audit, and clean-machine run;
- reuse example and known-failure table.

## Paper 4: open model integration and software paper

**Working title:** *An open, auditable fire-regime layer for spatial forest estate optimization*

**Target:** *Environmental Modelling & Software*; backup *Geoscientific Model Development* or JOSS
if the contribution is primarily software.

This paper is a methods/software paper, not a fire-science validation paper. It should cite Paper 1
for validation and Paper 2 for the optimization application, and it must not claim predictive skill.

## Shared experiments and sequence

1. **Event inventory:** collect independent TSA24 fire perimeters, years, dates, and weather.
2. **Support map:** derive from block geometry and validate against the archived support.
3. **Temporal/spatial splits:** pre-register; freeze.
4. **Calibration refit:** hierarchical/partial pooling with suppression-capacity covariates.
5. **Validation:** temporal, spatial, event-level, external benchmark.
6. **Fire-aware optimizer:** risk objective; near-global baseline; multi-seed.
7. **Data/software release:** raw resolver, manifests, DOI.
8. **Manuscripts:** write only after the evidence table is stable.

## Success criteria

A serious paper needs at least one of:

- independent validation that supports the model within pre-registered uncertainty;
- a rigorous negative/diagnostic result that explains the failure;
- a near-global optimization result showing a material fire-risk effect;
- a reusable data/software benchmark with demonstrated reuse.

A draft with only in-sample residuals, a sharded heuristic, or a single external case does not meet
that bar.

## Immediate next actions

- [ ] Build the independent TSA24 fire-event inventory (perimeters + dates + weather).
- [ ] Derive and validate the support map from block geometry.
- [ ] Pre-register the temporal and spatial validation protocol.
- [ ] Refit with suppression-capacity covariates.
- [ ] Add a fire-risk objective and near-global baseline.
- [ ] Archive raw-to-result pipeline with DOI.
