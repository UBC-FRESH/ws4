# P191 close-out: process schedule objective adapter

Date: 2026-11-13
Phase: P191 (#1130)
Branch: `feature/p191-process-objective`
Tasks: P191.1 (#1131), P191.2 (#1132), P191.3 (#1133)
Design note: `notes/design/ws4-process-objective.md`

## Result

The P190 final evaluation accounts can now be priced with the existing weighted-goal
objective. The adapter validates that a target fits the final-account level view and rejects
forms it cannot represent.

## What changed

- `evaluate_process_schedule` accepts `Target` values.
- `ProcessScheduleEvaluation` carries targets, objective, and per-target terms.
- Summary and JSON artifact include `objective`, `target_terms`, and `target_accounts`.
- Unsupported forms fail loudly: flow targets, risk aggregation, snapshot period, accumulating
  `product.` accounts, unknown accounts, and periods not ending at the final offset.
- Exact pass/fail and rejection tests.

## Evidence

- Evaluation tests: 9 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- 3 × 3 grid, one clearcut over fragments 1 and 2, one-year horizon, harvest area 20 ha:
  - minimum 30 ha: objective **10.0**, terms **(10.0,)**;
  - minimum 20 ha: objective **0.0**, terms **(0.0,)**.

## Boundary

- Final-account level targets only; multi-period and flow objectives are unsupported.
- The adapter does not run a search or replace the optimizer's account overlay.
- The volume bridge and harvest semantics remain provisional.
- The accounts are a reporting view, not the compiled management contract.

## Next

Let the optimizer call the process evaluator for candidate schedules. That requires a search
adapter and a decision about how many process runs a search can afford. The landscape-scale
WS4-vs-LBSE comparison remains blocked without an R/SpaDES reference run or published numeric
landscape output.

## Pull request

PR: #1134 is queued for maintainer approval. Do not merge without approval.
