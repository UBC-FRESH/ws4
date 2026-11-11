# Public fire corpus

Date: 2026-11-11
Phase: P165 (#985)

## Why the corpus exists

P164.2 ran the only two public observed-fire fixtures in the repository: Dogrib and Hay River.
Two cases are enough to exercise the code path, but not enough to estimate model skill, compare
regions, or support a regional validation claim. The two-case result is a harness check with a
data-gap caveat.

P165 builds a tiered corpus before any more calibration. The corpus is a data contract, not a
claim that every public fire can be forced into the model.

## Tiers

### Depth — hourly/FBP

A depth case has all of:

- observed or satellite-derived perimeter;
- hourly weather;
- ignition location and time, observed or explicitly reconstructed;
- a compatible FBP fuel map;
- terrain;
- provenance;
- documented licence/redistribution terms.

Depth cases test the hourly FBP path. They are expensive and few. The minimum for the corpus gate
is **3 fully ready independent depth cases**.

### Breadth — daily CFSDS

A breadth case has:

- CFSDS daily progression;
- daily weather;
- a compatible fuel map and terrain;
- provenance;
- documented licence/redistribution terms.

Daily cases do not test the hourly FBP path. They test whether the model's event distribution is
plausible across many fires, regions, and years. The minimum for the corpus gate is **20 fully
ready independent breadth cases**.

### Model-only

FireSTARR, BurnP3, and similar outputs are model-to-model evidence. They are never counted as
observed fires and never admitted to the observed-corpus gate.

## Status values

- `ready` — all required inputs present.
- `ready_with_limit` — usable, with a documented limit.
- `candidate` — potentially usable; inputs or provenance incomplete.
- `blocked` — needs a missing adapter or dataset.
- `rejected` — duplicate or otherwise inadmissible.
- `model_only` — model output, not observed evidence.

A `ready_with_limit` case may miss an input, but the missing field and the limitation are
explicit. A `ready` case may not.

## Admission rules

1. A case is admitted only after its tier, source, licence, inputs, and status are recorded.
2. Missing inputs are explicit; they are never inferred silently.
3. Duplicate events are rejected and excluded from the independent count.
4. Model-only cases are counted separately.
5. A case is independent only if it is not a duplicate and not rejected.
6. The gate counts fully `ready` cases only. `ready_with_limit` is reported separately.
7. Calibration does not resume until the gate passes.

## Current inventory

The registry lives in `ws4.fire.corpus` and is rendered to
`notes/reports/p165-corpus-manifest.json`.

| Case | Tier | Status | Missing inputs |
| --- | --- | --- | --- |
| Dogrib Scenario 2b | depth | ready_with_limit | licence |
| Hay River 2023_320 | depth | ready_with_limit | none |
| CFSDS 2023_321 | breadth | candidate | not acquired |
| CFSDS 2023_320 daily | breadth | rejected duplicate | none |
| WildfireAV US | depth | blocked | ignition, FBP fuel, licence |
| FireSTARR | model-only | model_only | n/a |
| BurnP3 | model-only | model_only | n/a |

The gate is **blocked**:

- fully ready depth: 0 of 3;
- fully ready breadth: 0 of 20;
- depth with limits: 2.

This is the intended result of the inventory. It makes the gap visible instead of promoting
candidates to ready.

## Acquisition plan

### P165.2 — depth

- Verify whether the Prometheus archive contains another complete sample.
- Check the CFSDS 2023_321 daily case for a defensible hourly weather stream and ignition.
- Record a no-go if no independent depth case can meet the contract.

### P165.3 — breadth

- Select 20 or more independent CFSDS events across years, regions, and sizes.
- Use daily progression as the documented basis.
- Define fuel/terrain crosswalks and their limits.
- Run a daily event check, not an hourly/FBP validation.

## Non-goals

- Treating two fires as a regional benchmark.
- Calling daily cases hourly/FBP validation.
- Counting model outputs as observations.
- Calibrating before the gate passes.
- Redistributing data whose licence is not documented.
