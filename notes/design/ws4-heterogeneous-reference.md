# Heterogeneous spatial reference

Status: implemented (P211)
Phase: P211 (#1222)
Date: 2026-11-14
Related: `notes/design/ws4-spatial-landscape.md`,
`notes/design/ws4-transition-alignment.md`

## 1. Purpose

P200/P210 used a uniform two-group landscape. P211 varies initial age and biomass across four
pixel groups, so competition, age mortality, and growth are exercised away from one uniform state.

## 2. Case

- 20 × 20 raster at 100 m, 400 pixels;
- one ecoregion;
- four pixel groups, two species each;
- initial ages 10–100 and B 500–5000 g/m²;
- 10-year horizon, 10-year succession timestep;
- fixed seed `20261114`.

## 3. Reference trajectory

| Year | Pixels | Biomass | ANPP | Mortality | Regeneration |
| --- | --- | --- | --- | --- | --- |
| 0 | 400 | 3750 | 0 | 0 | 0 |
| 0 after init | 400 | 4420 | 798 | 127 | 103 |
| 10 | 400 | 10822 | 928 | 342 | 1 |

Two independent runs produced byte-identical output.

## 4. WS4 comparison

The aligned process runs 11 annual updates on four matching fragments.

| Point | WS4 | Reference | Error |
| --- | --- | --- | --- |
| after init | 4420.0 | 4420 | 0 |
| year 10 | 10809.75 | 10822 | -0.113% |

The heterogeneous case supports the P210 transition alignment beyond the uniform case.

## 5. Evidence

- Script: `scripts/landis_heterogeneous_reference.R`.
- Fixture: `tests/fixtures/landis_heterogeneous_reference/`.
- Test: `tests/test_landis_heterogeneous_comparison.py`.

## 6. Limits

- Four hand-built pixel groups, not a real landscape.
- No regeneration or cohort-death bookkeeping in the WS4 process.
- No calibration or observed-data claim.
- The residual remains small but is not fully decomposed.
