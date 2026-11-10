# P163 close-out: fire behaviour completeness

Date: 2026-11-10
Parent issue: #971
Tasks: P163.1 (#972), P163.2 (#973), P163.3 (#974), P163.4 (#975)
Branch: `feature/p163-fire-behaviour-completeness`
Status: complete as model/proxy additions; PR queued for approval
Validation ladder: `notes/design/ws4-fire-validation-ladder.md`

## Result

P163 adds the missing behaviour vocabulary, a seeded spotting screening model, and
intensity-aware 3D tree outcomes.

### P163.1 — behaviour classes

- `ground`
- `surface`
- `passive_crown`
- `active_crown`

The class is recorded as `fire_behaviour` in the P156 event attributes. CFB thresholds are 0.1
and 0.9. Ground is a documented low-intensity/smoldering proxy, not a duff or peat combustion
model. Transition records are explicit.

### P163.2 — spotting

- Off by default.
- Seeded and replayable.
- Bounded landing distance and angular jitter.
- Every spot records source cell, target cell, ignition time, and distance.
- Labelled a **screening assumption**, not an operational forecast.
- No empirical calibration to an observed fire.

### P163.3 — tree outcomes and 3D

Tree outcomes:

- `unburned`;
- `scorched` — surface flame below crown base;
- `torched` — flame reaches the crown but not the top;
- `consumed` — flame reaches the tree top.

The viewer now keeps scorched crowns, shrinks and darkens torched crowns, and collapses
consumed crowns to a charred remnant. A verification run over the VRI demo produced:

- 12,588 trees;
- 10,938 burned trees;
- 10,870 scorched;
- 69 torched;
- 0 consumed;
- no page errors.

This is a visual class distribution, not a mortality validation.

## Validation status

Defensible:

- FBP surface/crown equations remain the validated source;
- standard-case and `cffdrs` comparisons are unchanged;
- spotting is deterministic and bounded.

Proxy / visual only:

- ground class;
- spotting transport and ignition;
- scorched/torched/consumed tree outcomes.

Missing:

- duff/peat combustion and smoldering spread;
- empirical spotting calibration;
- tree-mortality calibration;
- decision-grade burn-probability and treatment-effect validation.

## Accepted limits

- The ground class is a proxy, not a ground-fire process model.
- Spotting is a screening model with declared assumptions; it is not a forecast.
- The 3D outcomes are visual classes, not a mortality model.
- No observed-fire calibration or operational validation claim.
- The portal Fire workspace remains separate from the standalone public viewer.

## Recommendation

P163 is complete as a model-completeness phase, not as a validation claim. The next phase is
P164: decision-grade wildfire risk validation using the published multi-fire and
burn-probability benchmark ladder, treatment-effect evidence, and tree-mortality data.

A future fire-physics phase can replace the ground proxy and calibrate spotting only when
public observations support it.

## Pull request

PR: to be opened.
