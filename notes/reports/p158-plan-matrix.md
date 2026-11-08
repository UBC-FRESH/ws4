# P158.1 Plan scenario matrix

Date: 2026-11-08
Status: active
Branch: `feature/p158-plan-matrix`
Parent issue: #928
Task issue: #929

## Context

A WS4 scenario is a weighted goal programme, not a handful of independent constraints.
The Plan tab previously exposed flat target rows and only showed realized values through
pinned account charts. With 22 live TSA27 targets and 94 accounts, the target table used
44 table rows, hid weights/priorities/normalization in detail rows, and showed only a
status, not the realized value or gap.

## What this slice adds

- A Scenario matrix above the target charts:
  - one row per target account;
  - one column per accounting period;
  - target band, realized value, gap, and status in each cell;
  - flow marker, unit, active/off state, and account grouping;
  - sticky account column and horizontal period scrolling;
  - **Only failing** filter;
  - account-row click filters the target editor;
  - cell click selects that period and chart readout.
- Live consistency: the matrix re-renders with target/chart changes and live target
  updates.
- A browser regression test for matrix visibility, realized values, and failing filter.

## Verification

- `tests/test_pareto_browser.py::test_plan_scenario_matrix_shows_targets_and_realized`:
  passed.
- Live TSA27 preview at 1500×1000 and 1024×768:
  - 2 target accounts, 20 periods, 20 failing cells;
  - product target cells showed `≥6.00M`, realized `1.64M`, and `Δ-4.36M`;
  - feature stock target at P20 showed its band and realized value;
  - no page errors.
- Dashboard: `OVERALL: GREEN`.

## Next slices

P158.2 named scenarios and save-as/diffs; P158.3 batch account × period composer;
P158.4 penalty ledger and scenario comparison. The matrix deliberately remains read-only
for this slice so it can land independently of the target-file persistence redesign.
