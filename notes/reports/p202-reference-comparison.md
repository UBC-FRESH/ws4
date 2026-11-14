# P202 report: WS4-vs-Biomass_core spatial trajectory

Date: 2026-11-14
Phase: P202 (#1190)
Branch: `feature/p202-reference-comparison`
Design note: `notes/design/ws4-reference-comparison.md`

## Result

WS4 matches the P200 Biomass_core trajectory at year 1 but is 6.64% low at year 10.

## Evidence

- WS4 year 1: **2694.6167**; reference: **2694**.
- WS4 year 10: **8832.0582**; reference: **9460**.
- Relative year-10 difference: **-6.64%**.
- Test: `tests/test_landis_spatial_comparison.py` (2 passed).

## Root cause

The kernel equations are exact, but `LandisSuccessionProcess` applies a simplified annual
transition:

```text
B' = B + aNPPAct - mBio - mAge
```

Biomass_core applies the LANDIS transition:

```text
aNPPAct' = pmax(1, aNPPAct - mAge)
mBio'    = pmax(0, mBio - mAge)
mortality = mBio' + mAge
B'        = B + as.integer(aNPPAct' - mortality)
```

That is a deliberate double removal of `mAge`, plus floors and integer truncation. The module
also includes regeneration and its own cohort bookkeeping, which the current process does not.

## What this proves

- The P200 reference can be consumed by a WS4 regression test.
- The current process is not full Biomass_core parity, despite exact kernel functions.
- The mismatch is quantified, not hidden.

## What this does not prove

- It does not identify which single term explains the full 6.64%.
- It does not include regeneration or the module's integer bookkeeping.
- It does not validate against observed data.

## Next

Align the process transition with the published Biomass_core order, then re-run this comparison.
A successful fix should move year 10 toward 9460 without breaking the P199 kernel parity tests.
