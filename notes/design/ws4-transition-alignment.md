# LANDIS process transition alignment

Status: implemented (P203)
Phase: P203 (#1199)
Date: 2026-11-14
Related: `notes/design/ws4-reference-comparison.md`,
`notes/design/ws4-spatial-landscape.md`

## 1. Purpose

P202 found that WS4 matched the P200 Biomass_core reference at year 1 but was 6.64% low at
year 10. P203 aligns the annual process transition with the published Biomass_core order.

## 2. Transition changes

`LandisSuccessionProcess` now:

1. ages cohorts before growth (`age >= 1`);
2. computes `sumB` with the reference's initial `lastReg=0`;
3. computes age mortality before competition and ANPP;
4. applies `aNPPAct' = pmax(1, aNPPAct - mAge)`;
5. applies `mBio' = pmin(pmax(0, mBio - mAge), aNPPAct')`;
6. sets `mortality = mBio' + mAge`;
7. updates `B' = B + trunc(aNPPAct' - mortality)`.

The update no longer caps biomass at `maxB` directly; the competition equations enforce the
growth limit.

## 3. Comparison horizon

The reference output at year 0 is already after one growth update. Matching the year-10 row
therefore needs **11** annual updates: the time-0 update plus years 1 through 10.

## 4. Results

| Point | Before P203 | After P203 | Reference |
| --- | --- | --- | --- |
| year 1 | 2694.6167 | 2694.0 | 2694 |
| year 10 | 8832.0582 | 9444.0 | 9460 |

The year-10 difference is now **-0.169%**, down from **-6.64%**.

The residual 16 g/m² is consistent with the module's regeneration and bookkeeping that the
process does not yet implement.

## 5. Evidence

- `tests/test_landis_spatial_comparison.py`: 2 passed with the aligned values.
- `tests/test_ecosystem_landis.py` and `tests/test_ecosystem_ensemble.py`: 16 passed.
- The P199 kernel parity tests are unchanged.

## 6. Limits

- One toy landscape, one trait set, one horizon.
- Regeneration, cohort death bookkeeping, and full module state are still simplified.
- No calibration or observed-data claim.
