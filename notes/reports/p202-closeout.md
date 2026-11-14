# P202 close-out: WS4-vs-Biomass_core spatial trajectory comparison

Date: 2026-11-14
Phase: P202 (#1190)
Branch: `feature/p202-reference-comparison`
Tasks: P202.1 (#1191), P202.2 (#1192), P202.3 (#1193)
Design note: `notes/design/ws4-reference-comparison.md`
Report: `notes/reports/p202-reference-comparison.md`

## Result

The WS4 LANDIS process runs on the P200 initial cohorts and matches year 1 of the reference. At
year 10 it is 6.64% low. The mismatch is pinned by a regression test and traced to the simplified
process transition.

## What changed

- `tests/test_landis_spatial_comparison.py`:
  - builds the P200 two-species, two-fragment state;
  - runs ten annual LANDIS steps;
  - asserts year 1 = 2694.6167 and year 10 = 8832.0582;
  - asserts the -6.64% difference from the 9460 reference.
- Design note and spatial comparison report.
- LANDIS reference page updated.

## Evidence

- Comparison tests: 2 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Year 1: WS4 **2694.6167**, reference **2694**.
- Year 10: WS4 **8832.0582**, reference **9460**.
- Relative year-10 difference: **-6.64%**.

## Root cause

Biomass_core applies `pmax(1, aNPPAct - mAge)`, `pmax(0, mBio - mAge)`, mortality
`mBio' + mAge`, and integer truncation. WS4 applies `aNPPAct - mBio - mAge` once. The module
also includes regeneration and its own cohort bookkeeping.

## Boundary

- One toy landscape, one trait set, one horizon.
- The root cause is from reading the published R transition; no patched comparison yet.
- No calibration or observed-data claim.

## Next

Align the process transition with the published Biomass_core order, then re-run this comparison.
Year 10 should move toward 9460 without breaking the P199 kernel parity tests.

## Pull request

Merged as `282b6ea` (PR #1198); branch deleted.
