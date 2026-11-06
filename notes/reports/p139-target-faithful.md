# P139 target-faithful promoted runs

Date: 2026-11-06
Status: pr-open
PR: #839
Branch: `feature/p139-target-faithful`
Parent issue: #837
Task issue: #838

## Summary

P138 promoted a portfolio member's run into a direct run view, but the target status and
target series still read the service's live target file. A member's scaled weights could
therefore be displayed against a different target set.

This phase copies the member's target YAML into the promoted run, records its provenance,
and makes the run target endpoints prefer the run-local file.

## Changes

- Promotion resolves `member.targets` under the portfolio artifact, with a fallback to
  `run_dir/../targets.yaml`.
- The target file is linked/copied as `targets.yaml` in the promoted run.
- `portfolio_source.json` records `targets` and `targets_source`.
- Existing promoted runs are upgraded on repeated promotion if their target file is missing.
- `target_file_for_run` prefers `run_dir/targets.yaml` and falls back to the live file.
- Run target status, target series, and period width use the run-local file.
- `run_summary` exposes `portfolio_source`, and Plan shows a read-only notice for
  portfolio-member runs.

## Verification

- Promotion tests assert the target file copy, `targets_source`, run-local status
  (`below` against minimum 999), local target-series bounds, and summary source metadata.
- Chromium opens the promoted member in Plan and asserts the read-only member-target
  notice.
- Focused tests: 111 passed.
- `python scripts/dashboard.py`: `OVERALL: GREEN. Every gate passed.`
