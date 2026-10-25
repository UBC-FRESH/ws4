# P54: Environmental accounts (habitat and resilience)

Parent issue: `#375`
Branch: `feature/p54-environmental-accounts`
Status: planned (2026-10-25)

## Purpose

Make biodiversity, habitat structure, and landscape resilience first-class ws4
accounts. Carbon is already owned by P51 (`#357`); this phase covers the
non-carbon values.

## Children

- `P54.1` (`#376`): Dynamic Habitat Indices biodiversity account.
- `P54.2` (`#377`): forest structure habitat index from ALS.
- `P54.3` (`#378`): spatial resilience metrics.

## Accounting contract

Each account declares a name, unit, level/flow semantics, source, version, and
uncertainty where available. Level accounts are read at the period's end offset;
flow accounts are summed over the period. The carbon account in P51 is the
reference pattern; reuse it rather than inventing a second account surface.

## Out of scope

- Carbon. It is owned by P51 and FEMIC P115.
- A species-specific habitat model or a full SDM.
- An objective, constraint, or solver change. Risk-aware planning is `PLAN-01`.
- A fire-spread simulator.
- FEMIC P114 hydrology.

## Acceptance

- Each account is reproducible from the scenario and its declared inputs.
- DHI and structure habitat cover the AOI or report their gaps.
- Identical schedules produce identical resilience metrics.
- Every account appears in a report or web view.
- No objective or constraint changes are made in this phase.

## Risks

- Layer staleness and scale mismatch.
- Metric redundancy across the three resilience metrics.
- False precision: an index is not a species observation.
