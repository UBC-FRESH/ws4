# P203 close-out: aligned LANDIS process transition

Date: 2026-11-14
Phase: P203 (#1199)
Branch: `feature/p203-transition-alignment`
Tasks: P203.1 (#1200), P203.2 (#1201), P203.3 (#1202)
Design note: `notes/design/ws4-transition-alignment.md`
Report: `notes/reports/p203-transition-alignment.md`

## Result

The WS4 LANDIS process now matches the P200 Biomass_core spatial reference within **0.169%**
at year 10, down from **6.64%**.

## What changed

- Age cohorts before growth.
- Compute age mortality before competition and ANPP.
- Apply `pmax(1, aNPPAct - mAge)`, `pmax(0, mBio - mAge)`, `pmin(mBio, aNPPAct)`.
- Update biomass with integer truncation.
- Use 11 annual updates for the reference comparison (time 0 plus years 1–10).
- Update the comparison test and LANDIS evidence.

## Evidence

- Spatial comparison tests: 2 passed.
- LANDIS kernel and ensemble tests: 16 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Year 1: **2694.0** vs 2694.
- Year 10: **9444.0** vs 9460.
- Relative year-10 error: **-0.169%**.

## Residual

The remaining 16 g/m² is consistent with regeneration and cohort bookkeeping that the process
does not yet implement. It was not calibrated away.

## Boundary

One toy landscape, one trait set, one horizon. The process remains a simplified cohort
transition, not the full Biomass_core module. No observed-data claim.

## Next

Add regeneration and cohort-death bookkeeping, or move to a larger reference landscape. The
residual should be explained before claiming full module parity.

## Pull request

PR: #TBD is queued for maintainer approval. Do not merge without approval.
