# Open fire model reuse: Planscape review

Status: reviewed; planning input for P159
Date: 2026-11-09
Phase: P157 planning; proposed P159
Related: P157 (#923), BurnP3 comparison (#945), P159 (#946),
`notes/design/ws4-fire-behaviour.md`, `notes/reports/p157-closeout.md`

## 1. Question

What can WS4 reuse or reimplement from the Planscape project to move its fire
modelling and validation forward, especially for open fire-behaviour models?

## 2. Sources reviewed

| Source | Revision | Licence note |
| --- | --- | --- |
| `OurPlanscape/Planscape` | `40fdcf83c961dd302c7b03736b5f3b6a4257ff08` | CC0 1.0 public-domain dedication |
| `OurPlanscape/burn-emulator` | `181d845535ad02f0595988cd1a8a751321fdd83d` | No licence file in the reviewed commit; treat as all rights reserved |
| `pyregence/pyretechnics` | current public package | Community licence for qualifying noncommercial, research, educational, governmental, and nonprofit use; commercial use needs a separate licence |

Links:

- <https://github.com/OurPlanscape/Planscape/tree/40fdcf83c961dd302c7b03736b5f3b6a4257ff08>
- <https://github.com/OurPlanscape/burn-emulator/tree/181d845535ad02f0595988cd1a8a751321fdd83d>
- <https://github.com/pyregence/pyretechnics>

## 3. What Planscape itself contains

Planscape is a planning and optimization platform. It does not contain a fire
spread engine and it does not calibrate one.

Evidence from the reviewed commit:

- I found no FSim, FlamMap, Prometheus, FireSTARR, Rothermel, or Pyretechnics
  implementation in the Planscape source tree.
- Burn probability is handled as a precomputed data layer, not as a model that
  Planscape runs, validates, or tunes.
- The fire-adjacent code is an authenticated client for an external
  `burn-emulator` service. The client submits a treatment geometry, polls a
  job, and registers the returned raster. It contains no calibration or
  validation logic.
- The impact variables include fire-behaviour fields such as crown bulk
  density, canopy base height, canopy cover, fire-behaviour fuel model, flame
  length, rate of spread, and torching probability. These are treated as
  measured or modelled landscape attributes for treatment reporting, not as
  outputs of a model that Planscape calibrates.
- There are no observed-fire perimeters, hindcast harnesses, parameter-fitting
  routines, or calibration/validation splits in Planscape.

This is not a criticism of Planscape. It is a planning system above the fire
model layer; the model layer lives elsewhere.

## 4. What the burn emulator contains

The sibling `burn-emulator` repository is the useful part of the review. It is
a deep-learning surrogate of Pyretechnics, not a new physical fire model.

Its pipeline is:

1. Sample burnable ignition points across a variable-location polygon.
2. Run Pyretechnics with fixed fuel moistures, a fixed 10 km/h wind, 30 m
   cells, 60-minute steps, and an 8-hour maximum duration.
3. Treat those synthetic burns as training labels.
4. Train a CNN with circular kernels to predict per-pixel fire type.
5. At inference, stamp the predicted fire shapes across a landscape to form a
   conditional burn-probability raster.
6. Report crown-change fractions inside and outside a treatment area.

The implementation has two global adjustment factors, `fuel_spread` and
`weather_spread`, both defaulting to `1.0`. They are not fitted to observed
fires, and no objective function or parameter search is present.

The most important finding is the evaluation gap. The core evaluation path
writes predictions to disk and leaves quantitative evaluation metrics as a
TODO. The repository can compare a deep-learning prediction with a
Pyretechnics run, but it does not score that comparison in the core evaluation
code and it does not compare either model with observed fire perimeters.

So the burn emulator provides:

- a reproducible synthetic-corpus pattern;
- a fast surrogate experiment;
- provenance fields for model, inputs, and runtime;
- a cache and job API for expensive fire runs.

It does **not** provide:

- an observed-fire calibration method;
- a validation metric against real fires;
- a Canadian FBP implementation;
- a reason to treat Pyretechnics output as ground truth;
- a model that predicts perimeter directly. Its output is crown-change
  fraction, not a fire perimeter.

## 5. Pyretechnics as a possible cross-check

Pyretechnics is a Python library for the fundamental equations used by
GridFire, ELMFIRE, FlamMap, FARSITE, FSIM, and BehavePlus. It includes surface
fire, crown fire, spot fire, cell burning, and an Eulerian level-set spread
algorithm. That makes it a credible model-to-model cross-check for WS4's
Rothermel and FBP layers.

It is not a drop-in Canadian model:

- Its bundled fuel models are the US FBFM family, not the 17 Canadian FBP
  types.
- A Dogrib run would need an explicit FBP-to-FBFM crosswalk, and that crosswalk
  would be an assumption, not a calibration.
- Its licence is a community/commercial licence, not an OSI open-source
  licence. WS4 can only adopt it after a licence review for the intended use.
- Its default moisture and wind assumptions in the burn emulator are fixed
  scenario constants, not observations.

The honest use is a standard-case and model-to-model comparison, not an
observed-fire validation.

## 6. Decision for WS4

### 6.1 What to reproduce

A **WS4-native surrogate feasibility study** is worth one bounded phase. It
reproduces the useful idea, not the code:

- generate a deterministic synthetic burn corpus from the WS4 FBP
  surface/crown/growth kernel;
- train a compact surrogate on that corpus;
- evaluate on held-out synthetic runs;
- evaluate Dogrib as out-of-distribution evidence, never as training data;
- publish a model card with kernel version, fuel/weather/grid versions, seed,
  training range, failure modes, and licence limits;
- gate any UI or web integration on an explicit error threshold.

This is P159 (#946).

### 6.2 What not to reproduce

- Do not copy the Planscape CNN, training code, California fuel assumptions, or
  service implementation. The burn-emulator repository has no licence file in
  the reviewed commit, and the model is not validated against observed fire.
- Do not use a surrogate as a substitute for the P156 kernel in validation.
  The kernel remains the auditable model.
- Do not call a Pyretechnics comparison a calibration. It is model-to-model
  evidence.
- Do not fit parameters to Dogrib and then report Dogrib as validation. One
  fire cannot be both the calibration and the holdout.

### 6.3 What remains blocked

**Observed-fire calibration protocol.** A credible calibration needs at least
two independent fires: one for fitting and one for holdout. It also needs
explicit parameter bounds, a declared objective, and a weather/fuel/ignition
provenance record. Dogrib remains a validation case, not a fitting target. This
is recorded in the backlog as blocked on a second independent fire.

**Pyretechnics cross-check.** This is blocked on a licence decision and a
documented Canadian fuel crosswalk. If both clear, the first experiment should
be standard-case and model-to-model comparison against WS4, not a Dogrib
calibration.

## 7. P159 acceptance boundary

P159 succeeds even if the surrogate is rejected. The required result is a
measured yes/no:

- held-out synthetic footprint and fire-state error;
- Dogrib out-of-distribution error using the P157 metrics;
- training and inference cost;
- a model card that states the data range and failure modes;
- a decision to integrate or stop.

No web dependency, no claim of operational validity, and no observed-fire
calibration claim may precede that gate.
