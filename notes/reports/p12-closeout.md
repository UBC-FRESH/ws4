# Phase close-out report: P12, spatial decision match

Phase issue: #120. Branch: `feature/p12-spatial-decisions`. Roadmap: `ROADMAP.md`, "Phase 12: Spatial
decision match". Parent pull request: the phase's own.

P11 verified that the **values** match — 1,383 account-period and flow values reproduced on both 2026
scenarios, routing parity on all 25,134 node-and-mill pairs, 959 yield-curve points, a patch family
compared over 630 cells. P12 took the replacement claim from there to the **spatial decisions**: the
places where the reference makes a choice WS4 does not, each one closed, compared, or refused with the
measurement that says why.

## Recommendation

**Close P12.** Every acceptance criterion is met, five of them by a comparison and three by a measured
reason with the instrument built and tested for the day the input exists. The one thing P12 could not
finish — the patch components — is not finishable against this reference, and that is now established
rather than assumed: everything Patchworks can export has been exported, and its patch reports are class
aggregates and its maps are images.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| The reference's harvested patch family is compared, or has a measured reason it cannot be | the criterion is a *product*, and resolving one is not a lookup: with the key the product's values land at the **wrong time** — a block the schedule harvests in year 44 had its value appear in year 150 — so it is **refused** with that reason, and the lookup is not the problem. The young family is compared, 630 cells over six quantities | met by refusal with the reason measured |
| The mill products' split is decided the same way in both tools, and the route ratios compared | the reference's rule is read from its own model: conifer may reach either mill, **deciduous Mill 2 only** — WS4 had been sending **62.7% of the deciduous area** to a mill the reference never uses. With that declared, `product.Mill2.Yield.Decid` agrees to **4 units in 2.78 million**, and WS4's rule matches the reference's own exported choice on **12,266 of 13,377 conifer block-periods (91.7%)**. What is left is the reference's Mill 1 **delivery target**, recorded for the parity mode | met; the ratios' remaining gap is named |
| The route report states the model's period width, and its columns are comparable per period | `period_width` was loaded and never used; it now reaches the ledger, the report folds into the model's periods and is written **per destination** too. Against the reference: `VOLUME` is the same quantity (8% and 10%, which is #122's policy), `AVERAGEHAULDIST` is a **unit**, `BUILTLENGTH` was a defect — and `LENGTH` is recorded as the one quantity not explained, with the candidate reason marked unverified | met, with the comparison recorded column by column |
| The attractor is reported as the reference defines it, or the difference is measured | from the reference's own 360 values it is a per-class landscape quantity and a lower quantile of the class's patch sizes, **not** the size share its documentation invites (0.26 to 2.57 off, cell by cell), and **not** a function of the six published sub-accounts (9% median, 58% worst residual). So WS4 **refuses** it rather than keeping a `1.0` flag that was not a value | met by measurement |
| A parity mode exists that enforces the reference's readings, with each deliberate divergence named and its effect documented | **parity is the default**; what WS4 computes differently is named under a route configuration's `divergences`, one entry per quantity, and an unknown entry is refused rather than ignored. One entry: traffic-weighted maintenance, `f(0)=0` and `f(x>0)=b+a·x`, measured at **+4.2%**, **+42.4%** and **×5.24** of parity | met |
| The patch components are compared, or have a measured reason they cannot be | the instrument is built and tested — WS4 states its own components as `patch_membership.csv`, `compare_patch_components` compares partitions and is tested against a listing with a **known** difference — and the `patchcomponents` check **skips with the evidence** on every run, because the reference cannot state membership | met by a measured ceiling |
| The dashboard green at every commit, with the docs and docstrings gates | seven gates GREEN at each of the five evidence heads, and at the phase head | met |

## 2. What shipped

- **P12.1** (#121, `c602735`) — a patch criterion that is a product is refused, with the reason
  measured, and a label that is neither a feature nor a product is refused too.
- **P12.2** (#122, `a1fd71e`) — the destination decisions are compared, block-period by block-period,
  for the first time: the reference's declared splits are read from `analysis/C5.pin`, WS4's model is
  built from them, and the mill products are compared period by period. The surplus account became
  declarable **per product**.
- **P12.3** (#123, `80071ad`) — the route report is folded into the model's periods and written per
  destination, `period_width` reaches the ledger, and a per-destination defect (`BUILTLENGTH` never
  recorded) was fixed. The report is what exposed that **27 products were being routed as wood**; a map
  that names products is now also the list of what is delivered.
- **P12.4** (#124, `f41dcd5`) — the attractor is established from the reference's own values and refused
  rather than faked; the `1.0` flag and its field are gone.
- **P12.5** (#125, `67408cf`) — the parity mode, with traffic-weighted maintenance behind it, and the
  route accounts' maintenance charge fixed to agree with the report (**1.0000**, from 7.0×).
- **P12.6** (#126, this head) — the component comparison, its tests, WS4's own membership listing, and
  the ceiling recorded with its evidence.

## 3. Gate evidence

At the phase head: `lint` GREEN, `format` GREEN, `types` GREEN, `tests` **563 passed**, `validator`
GREEN, `docs` GREEN, `docstrings` GREEN. The reference acceptance run on the 2026 sample: `parity PASS`
(25,134 pairs), `destinations PASS`, `patchcomponents SKIP` (with the ceiling named), `accounts PASS`
(1,383 values), and the examples show **0 drift** over 47 compared cells.

## 4. CI evidence

| Run ID | Head commit | Conclusion |
| --- | --- | --- |
| (the pull request's own runs) | see the pull request | the four jobs, green |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| A patch criterion that is a product was **refused**, not implemented | the lookup was not the problem: keyed correctly the series is no longer zero, but its values land ten years late — a wrong value that looks right is worse than a zero that looks like a zero | refused with the measurement; the real fix, the product on the treatment's own timeline, is in the backlog |
| The **attractor** was refused, not approximated | its value is a per-patch statistic the export does not determine | refused with the evidence; the class's size share, which the documentation invites, is 0.26 to 2.57 times it |
| The parity mode is one named entry, not a framework | a mode multiplies the surfaces that must stay honest | the smallest version that makes a divergence explicit; quantities that agree are not declared at all |
| Two claims in the parity note were **wrong and are corrected** | the mill splits were compared one of WS4's *years* against one of the reference's *periods*, which made them look nearly opposite; they are 66/34 against 62/38 | re-measured like for like and rewritten |
| The route accounts charged maintenance 7.0× the report | the accounts charged it per produced product while the report charged it per segment per period | one charge, computed after every flow of the period is in; 1.0000 on MILL 1 |
| The optimizer's incremental route path over-counted per-segment charges | it prices route accounts as a per-block sum | it defers to the full simulation for `build` and `maintain`, and tests pin both paths |
| **27 products were being routed to the mills as wood** | a product with no eligibility entry went to every destination | an eligibility map that names products is now the list of what is delivered; the report's volume went from 2.26× the reference's to 8% |
| The harvested family, the attractor and the components remain out | the reference cannot state patch membership, and everything it can export has been exported | recorded as the ceiling, with the instrument built and tested so the comparison is a wiring job when a listing exists |

## 6. What remains, and where

The replacement claim is now verified at the level the roadmap asked for: the values and the spatial
decisions, with each deliberate divergence named and measured. What P12 leaves is in `notes/backlog.md`,
each with its blocker named:

- **the patch criterion on the treatment's own timeline** — the real fix for the harvested family;
- **patch membership** — the ceiling above; the components and the attractor both wait on it;
- **the reference's Mill 1 delivery target** — a planning decision, the natural second entry in
  `divergences`;
- **what the reference's route report `LENGTH` counts** — the one quantity P12 could not explain;
- **the route report's distance unit** — metres against kilometres, a report decision rather than a
  comparison one.

## 7. Decision

Close P12: its acceptance criteria are met, the phase's own evidence is the acceptance run and the
dashboard, and the three items that could not be compared are recorded with the measurements that say
why rather than with an expectation that they might be.
