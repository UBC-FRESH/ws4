# P158.3 Plan batch target composer

Date: 2026-11-08
Status: active
Branch: `feature/p158-batch-composer`
Parent issue: #928
Task issue: #931

## Summary

The Plan workspace now has a batch target composer under the account browser. It uses the
existing multi-select account tray and writes multiple target rows in one request.

Supported fields:

- one or more selected accounts;
- start and end period, all-periods toggle, and period width;
- level band, minimum-only, maximum-only, and even-flow modes;
- minimum/maximum, min/max weights, priority, and normalization;
- duplicate detection and a preview of up to eight rows;
- immediate update of the target table and scenario matrix after saving.

## Verification

- New browser test: `test_plan_batch_targets_adds_multiple_accounts_and_periods` passed.
  It selects two accounts, adds a P6 level band, and confirms the target table grows.
- Local TSA 27 preview: the batch composer added four targets across two accounts and two
  periods; the target file grew from 22 to 26 rows and the matrix reported the new target
  cells.
- No browser page errors.
- Dashboard: `OVERALL: GREEN`.

## Limits

- The composer writes the live target file immediately. Named drafts, save-as, and diffs
  remain P158.2.
- Even-flow mode creates one guard row per selected account, not a full multi-period level
  pattern.
- Undo/redo and target templates are P158.4/P158.5.
