# Fire-model validation ladder and P163 plan

Status: planning note
Date: 2026-11-10
Related: P157 (#923), P159 (#946), P160 (#947), P161 (#954), P162 (#961), P163 (#971)

## 1. Why this note exists

WS4 should not judge a fire model by one historical perimeter or by a single “best-in-class”
IoU. Published event-level validation is modest, variable, and strongly conditioned on inputs.
The model needs a validation ladder tied to the decisions it supports.

## 2. Published reference points

These are examples, not universal thresholds.

| Model / study | Result | Use |
| --- | --- | --- |
| ELMFIRE, WildfireAV multi-fire | mean Jaccard 0.178, Sorensen 0.278, kappa 0.241 | Event-level state of practice |
| FARSITE, WildfireAV multi-fire | mean Jaccard 0.176, Sorensen 0.274, kappa 0.249 | Event-level state of practice |
| Prometheus, Dogrib case 4 | Figure of Merit 0.21 at 200 m | Difficult Canadian event |
| Prometheus, Dogrib case 3 | FoM 0.568 | Better-conditioned event |
| ABWiSE synthetic/easy cases | FoM 0.48–0.83 | Easy or synthetic cases |
| FSim annual BP, California | 56.7–79.8% of burned area in top 20% BP; LSS 0.114–0.339 | Probabilistic risk benchmark |
| FOFEM/Ryan tree mortality | stand-level within ±20% for most western conifers | Tree-effect benchmark |

Implications:

- IoU/Jaccard around 0.2 is normal for real event reconstruction.
- 0.3–0.4 is good.
- 0.5–0.8 is easy-case or well-conditioned performance.
- Area and perimeter biases of tens of percent are normal.
- A planning model can be useful with modest perimeter overlap if its risk ranking and
  treatment response are calibrated.

## 3. Validation ladder

### Tier 1 — Physics and standard cases

Must pass:

- Rothermel/Anderson standard cases;
- FBP/cffdrs surface, crown, and moisture cases;
- ellipse growth and monotonicity;
- deterministic replay.

This is exact or near-exact and is not negotiable.

### Tier 2 — Event reconstruction

Use multiple fires and the same inputs. Compare against:

- accepted models on the same fire;
- published distributions, not the best run;
- median, spread, and worst case.

Report area bias, perimeter bias, centroid, IoU/Jaccard, Sorensen, orientation, and uncertainty.
A single fire remains an anecdote.

### Tier 3 — Probabilistic risk

For planning:

- burn-probability reliability and discrimination;
- Brier/logarithmic skill scores;
- burned area captured in top BP classes;
- temporal and spatial calibration.

The FSim benchmark class is the target, not a perimeter IoU.

### Tier 4 — Treatment response

The core WS4 product:

- direction and magnitude of stand and landscape treatment effects;
- comparison with experiments, meta-analyses, and operational evidence;
- sensitivity to fire-model error;
- whether treatment rankings flip under plausible uncertainty.

A model that reproduces one perimeter but ranks treatments incorrectly is not useful.

### Tier 5 — Tree-level fire effects

Use the Fire and Tree Mortality Database and FOFEM/Ryan-type relationships:

- crown scorch, bole char, bark thickness;
- tree mortality probability;
- stand-level ±20% as a realistic benchmark;
- individual-tree uncertainty made explicit.

### Tier 6 — Decision quality

For the integrated planner:

- Pareto front quality;
- regret against a full-scenario oracle;
- risk-constraint satisfaction;
- stability under fire-weather uncertainty;
- sensitivity of treatment rankings.

## 4. What “good” means

A model is good enough when:

1. it passes Tier 1;
2. its event behavior is inside the published envelope or its differences are explainable;
3. its risk probabilities are calibrated enough for ranking;
4. its treatment effects have the right sign and plausible magnitude;
5. its uncertainty is visible to the planner;
6. its decision rankings are stable under plausible error.

It is not good because one fire has a high IoU.

## 5. P163 — fire behaviour completeness

P163 adds the missing physical classes without claiming operational validation.

### P163.1 Ground, surface, passive crown, active crown

Add `FireBehaviourClass`:

- `GROUND` — explicit low-intensity/smoldering proxy, not a duff-combustion model;
- `SURFACE` — flaming surface fire, no crown;
- `PASSIVE_CROWN` — intermittent/passive crown fire;
- `ACTIVE_CROWN` — active crown fire.

The existing FBP crown fraction and flame length drive the class. Transitions are recorded so
the surface-to-crown jump is explicit. The ground class is a proxy: WS4 does not yet model
duff/peat combustion, smoldering spread, or residual heat.

### P163.2 Spotting

Add a bounded, seeded spotting contract:

- lofting, transport, landing, ignition;
- public analytic/empirical basis;
- off by default;
- every spot records its parent and distance;
- labelled a screening approximation, not a forecast.

### P163.3 Intensity-aware tree effects and 3D

Tree outcomes:

- `unburned`;
- `scorched` — surface heat, crown not consumed;
- `torched` — crown consumed but trunk remains;
- `consumed` — severe consumption.

The viewer should show low surface flame, passive torching, and active crown fire differently,
not one uniform “burned crisp” state. These are visual classes, not a validated mortality model.

### P163.4 Verification

Separate:

- exact standard-case evidence;
- model-to-model evidence;
- visual/proxy classes;
- missing physics.

## 6. P164 — decision-grade risk validation (planned)

P164 will replace single-fire perimeter pass/fail with the Tier 2–6 ladder:

- multi-fire event benchmark;
- burn-probability calibration;
- treatment-effect validation;
- uncertainty propagation into the multi-objective planner;
- decision-quality metrics.

No P164 work starts until P163 is closed or explicitly deferred.
