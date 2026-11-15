# Age-based volume curves

Status: implemented (P231)
Phase: P231 (#1326)
Date: 2026-11-15
Related: `notes/design/ws4-shared-schedule.md`

## 1. Purpose

P230 compared a linear biomass bridge with the estate yield curve. P231 lets the bridge use the
same age-based curve as the estate fixture.

## 2. Contract

`VolumeBridgeConfig.age_volume_curves` maps species to age-to-volume-per-hectare values.

- Ages are non-negative integers.
- Values are finite and non-negative.
- Ages are sorted.
- A species with a curve uses it instead of the biomass rate.
- Ages between points interpolate linearly; ages outside the range clamp to the endpoint.

The curves are included in the JSON parameter artifact.

## 3. Shared-schedule result

`PL` curve: `0 -> 0`, `40 -> 120`, `60 -> 170`.

- estate `feature.Volume` after CC on block 1: **340**;
- process `bridge.volume_m3` after the same CC: **340**;
- P223 absolute difference: **0**.

## 4. Evidence

- `tests/test_ecosystem_bridge.py`: 8 passed (including interpolation, clamping, serialization,
  and invalid curves).
- `tests/test_process_estate_shared_schedule.py`: 1 passed.
- Full dashboard: **OVERALL: GREEN**.

## 5. Limits

- Test curves, not a compiled management yield table.
- No fire, succession, or regeneration in the shared-schedule case.
- Not an observed-data validation.
