# P150 GPU effect-table extension guard

Date: 2026-11-08
Status: complete
Branch: `fix/gpu-extension-guard`
Parent issue: #886
Task issue: #887
Merge commit: `2c18e19`

## Summary

The TSA 29 lean effect table is target-coupled: 42,483,063 rows over 200 harvest-volume
cells. Adding the managed-stock feature cell through `EffectTable.extend_cells` prices
every candidate row. The live attempt ran for more than nine minutes, reached 36 GB RSS,
and was stopped.

A lazy per-run extension is not viable at that scale. `EffectTable.extend_cells` now
refuses an extension when the table has more than `max_extension_rows` rows (default
5,000,000) and tells the caller to build a target-independent cell basis or a
factorized archive. The existing byte guard still handles wide extensions.

## Verification

- Real TSA 29 table: `42,483,063` rows; the guard raises immediately with the row count.
- `tests/test_gpu_effects.py`: 14 passed.
- TSA 29 `base` profile, zero generations, harvest-only target: objective
  `1311809142.7037165`, verified objective `1311809142.7037134`,
  `exact_match: true`, 48.35 seconds, 7.3 GB RSS.
- The managed-stock default was resolved in P154: the TSA 29 base profile now uses a
  factorized stock basis and reports exact GPU replay. See `p154-tsa29-stock.md`.

Dashboard: `OVERALL: GREEN`.
