# P158 close-out: Plan scenario workspace

Date: 2026-11-09
Status: complete
Branch history: `feature/p158-plan-matrix`, `feature/p158-batch-composer`,
`feature/p158-scenarios`, `feature/p158-penalty-ledger`
Parent issue: #928

## Result

P158 is complete. The Plan workspace now supports scenario definition and observation as
a multi-target surface.

- Scenario matrix: all target accounts and periods with bands, realized values, gaps,
  status, flow markers, and failing-only filtering.
- Batch target composer: multi-account, period ranges, level/min/max/even-flow modes,
  weights, priority, normalization, duplicate detection, and preview.
- Scenario library: named validated snapshots, load into the editor without changing live
  targets, reload live, delete, and a diff against the live target file.
- Penalty ledger: priority-weighted target penalty ranking with realized value, gap,
  weights, priority, objective share, status, flow penalties, and binding-only filtering.
- API and browser tests for the matrix, batch composer, scenario library, target diff, and
  ledger.

## Verification

- Dashboard: `OVERALL: GREEN`.
- CI: all gates green on the merged slices.
- P158.5 local TSA27 regression:
  - viewport widths 1500, 1200, and 1024;
  - no document-level horizontal overflow;
  - matrix and penalty ledger both render;
  - 2 matrix rows and 22 ledger rows;
  - scenario bar, target diff, and batch controls present;
  - no browser page errors.

## Remaining limits

- At 1024×768 the Plan sidebar still requires scrolling to reach the full target table;
  the matrix and ledger remain visible in the main pane.
- The penalty ledger uses the last completed run's target evaluation; live penalty values
  are not recomputed during a running search.
- Scenario metadata is intentionally lightweight: name, description, timestamp, target
  count, and source. Cross-scenario run comparison remains a future slice.
