# Phase close-out report: P13 The reference's remaining readings

Phase: P13 The reference's remaining readings
Parent issue: #128
Pull requests: #130 (`P13.1`), #132 (`P13.2`); the last two items were closed by P17's route-report
work (`#148`, `#149`)
Evidence head: `9a1770b`, plus the report commit
Date: 2026-10-20
Status: closing.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A patch criterion that is a product, on the treatment's own timeline | P13.1 merged; the harvested family compares in aggregate (area 0.92, count 1.48) | met |
| The reference's delivery target for its mill products | P13.2 merged; the mechanism is implemented and measured **not** to close the split — the reference's numbers are a search outcome under soft bounds | met, with the measurement |
| The route report states its distance in a unit it names | `AVERAGEHAULDIST` now reported in kilometres, the reference's unit (P17.6) | met |
| What the reference's route report `LENGTH` counts | resolved: the **distinct road used in the period**, counted once; WS4's report now matches that definition (`#148`) | met |

## 2. What remains unverifiable against this reference

- **Patch membership** — the ceiling P12.6 established; the components and the attractor wait on it.
- The reference's own road set is known, but per-segment construction parity is not required and was
  never a P13 criterion.

These are recorded in `notes/backlog.md`, not asserted as met.

## 3. Next phase

P17 finished the route-report items; P18 (the web front end) is next. Closing P13 with its two
deferred items named.

## 4. Decision

- [x] Approve as written.
