# Shared-schedule process/estate comparison

Status: implemented (P228)
Phase: P228 (#1313)
Date: 2026-11-15
Related: `notes/design/ws4-account-comparison.md`

## 1. Purpose

P223 compares account files; P228 runs the same schedule through both engines and feeds their
final accounts into that comparison.

## 2. Case

- Committed synthetic estate fixture: block 1 (3 ha), block 2 (2 ha).
- Schedule: `CC` on block 1 at offset 0.
- Estate simulator: natural `feature.Volume` drops from 700 to 340.
- Process engine: two fragments, no-op succession, fire off, regeneration off, supply management.
- Provisional linear volume bridge: 1 m3 per t of live biomass, merchantable fraction 1.

After the harvest the process state has fragment 2 only: 170 t/ha × 2 ha = 340 m3.

## 3. Result

The mapped process `bridge.volume_m3` and estate `feature.Volume` are both **340 m3** at the final
offset. The P223 comparison reports absolute difference **0**.

The test writes `account_comparison.json` as evidence.

## 4. Evidence

- `tests/test_process_estate_shared_schedule.py`: 1 passed.
- Both engines run the same CC schedule.
- Mapped final volume matches exactly.

## 5. Limits

- Synthetic fixture and provisional linear volume bridge.
- No fire, succession, regeneration, or real yield curves in this comparison.
- This is an account-contract comparison, not a model-skill validation.
