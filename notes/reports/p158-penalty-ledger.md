# P158.4 Plan penalty ledger

Date: 2026-11-09
Status: active
Branch: `feature/p158-penalty-ledger`
Parent issue: #928
Task issue: #935

## Summary

Plan now has a **Penalty ledger** beneath the scenario matrix.

- Ranks active targets by priority-weighted penalty.
- Shows account, period, target band, realized value, gap, min/max weights, priority,
  penalty, share of total objective, and status.
- Includes flow targets with their actual aggregated flow penalty.
- **Binding only** filters to targets currently outside their band.
- Reflects the run's realized target evaluation rather than recomputing the solver.

## Verification

- Browser test: ledger is visible, has rows, reports bindings, and the binding-only filter
  keeps at least one row.
- API test: flow targets now return a numeric penalty in `/api/runs/{run}/targets`.
- Dashboard: `OVERALL: GREEN`.

## Limits

- The ledger is based on the last completed run's target evaluation; it does not update
  penalty values during a live search until the run writes new target data.
- Scenario comparison across two runs remains a follow-up.
