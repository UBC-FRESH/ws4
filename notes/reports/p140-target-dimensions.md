# P140 target-row dimensions for 5-7D scans

Date: 2026-11-06
Status: pr-open
Branch: `feature/p140-target-dimensions`
Parent issue: #840
Task issue: #841

## Summary

The guided scan builder previously listed one option per unique account. TSA27 has a
single target account but 21 periodic target rows, so the builder could only make a
one-dimensional weight scan.

The builder now lists target rows as dimensions:

- account-level rows use `account`;
- periodic rows use `account@period`;
- labels include the period and end year;
- a **+5 periods** or **+7 periods** action replaces the scan with that many temporal
  dimensions from the selected account (or the first periodic rows when the selected
  account has fewer).

This changes only the weight-scan expression. The target bounds, live target file, and
optimizer semantics are untouched.

## Verification

- Browser test builds an account@period scan, asserts the generated `vary` string,
  scaffolds five periods, and opens the explorer.
- Existing parser tests already cover `account@period`.
- `python scripts/dashboard.py`: `OVERALL: GREEN. Every gate passed.`

## Limits

- Temporal dimensions are not the same as multi-account objective dimensions.
- A 5-7D grid is sampled with the existing bounded grid/random policy.
