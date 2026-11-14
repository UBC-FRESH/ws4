# WS4-vs-Biomass_core spatial trajectory comparison

Status: implemented (P202)
Phase: P202 (#1190)
Date: 2026-11-14
Related: `notes/design/ws4-spatial-landscape.md`,
`notes/design/ws4-landis-r-parity.md`

## 1. Purpose

P200 captured a 10-year spatial Biomass_core trajectory. P202 runs the WS4 LANDIS process on the
same initial cohorts and quantifies the difference. This is a diagnostic, not a fix.

## 2. Setup

The WS4 state has two fragments, each with two cohorts:

- `Pice_Gla`, age 20, B 1000;
- `Popu_Tre`, age 30, B 1000.

The traits match the P200 reference. The process uses `succession_timestep=10` and
`stage="nonSpinup"` for 10 annual steps.

## 3. Result

| Year | WS4 mean biomass | P200 reference |
| --- | --- | --- |
| 1 | 2694.6167 | 2694 |
| 10 | 8832.0582 | 9460 |

Year 1 matches to the reference rounding. Year 10 is **-6.64%** below the reference.

The current behavior is pinned by `tests/test_landis_spatial_comparison.py`.

## 4. Why the mismatch exists

The kernel functions are exact (P199), but the full Biomass_core transition is not the same as
`LandisSuccessionProcess`:

Biomass_core does, per annual cohort update:

1. `aNPPAct' = pmax(1, aNPPAct - mAge)`;
2. `mBio' = pmax(0, mBio - mAge)`;
3. `mortality = mBio' + mAge`;
4. `B' = B + as.integer(aNPPAct' - mortality)`.

This is the LANDIS source's deliberate double removal of `mAge`, plus integer truncation.

WS4 currently computes:

```text
B' = B + aNPPAct - mBio - mAge
```

It removes `mAge` once, does not apply the `pmax` floors, and does not truncate to integer.
Biomass_core also includes regeneration and its own cohort bookkeeping.

## 5. Limits

- One toy landscape, one trait set, one 10-year horizon.
- The root-cause list is based on reading the published R transition; it is not yet a patched
  and re-run parity test.
- No calibration or observed-data claim.
- The next phase should align the process transition and re-run this comparison.
