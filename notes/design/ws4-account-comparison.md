# Process/estate account comparison

Status: implemented (P223)
Phase: P223 (#1292)
Date: 2026-11-15
Related: `notes/design/ws4-optimizer-risk-bundle.md`

## 1. Purpose

The process engine and estate optimizer do not share account names by default. P223 adds an
explicit, validated mapping and compares final-period values. It measures the bridge without
pretending the account systems are identical.

## 2. Contract

`compare_accounts` takes:

- process account values (`offset`, `account`, `value`);
- estate account values (same columns, optional `scenario`);
- an explicit process-to-estate account mapping;
- optional scenario selection.

It reports final offsets, per-account values, absolute difference, and relative difference. A zero
estate value omits the relative difference.

## 3. Exact evidence

Process `bridge.volume_m3=100` vs estate `feature.Volume=120`:

- absolute difference `-20`;
- relative difference `-0.166666...`.

The JSON/CSV artifact records the same values.

## 4. Limits

- One final period, one explicit mapping.
- No default mapping.
- No engine runs in this module.
- No calibration or observed-perimeter validation.
