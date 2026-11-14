# P195 close-out: end-to-end process optimization

Date: 2026-11-14
Phase: P195 (#1150)
Branch: `feature/p195-process-optimization`
Tasks: P195.1 (#1151), P195.2 (#1152), P195.3 (#1153)
Design note: `notes/design/ws4-process-optimization.md`

## Result

The process search loop now closes in one API: a schedule grammar, the P193 hill-climb, and the
best P190/P191 evaluation with its artifacts. The grammar also supports optional offset moves
while keeping its default add/remove behavior unchanged.

## What changed

- `ScheduleMoveGrammar.allow_offset_moves`:
  - moves each existing event to every other unused offset on its block;
  - deduplicates against add/remove neighbours by canonical schedule id;
  - defaults to false.
- `ws4/opt/process_optimization.py`:
  - `optimize_process_schedule`;
  - `ProcessOptimizationResult`;
  - best schedule/accounts summary;
  - search, best-evaluation, and JSON artifact writer.
- Exact offset-move, wrapper, determinism, validation, and artifact tests.

## Evidence

- Optimization tests: 4 passed.
- Grammar tests: 7 passed.
- Neighbourhood and candidate-search tests still pass.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- 3 × 3 grid, 20 ha harvest target: best schedule is the full block-1 harvest, objective 0.
- Offset moves on `{1: (CC, 0), (CC, 1)}` with a three-year horizon add:
  - `{1: (CC, 1), (CC, 2)}`;
  - `{1: (CC, 0), (CC, 2)}`.

## Boundary

- Caller-supplied block universe and treatments.
- No treatment-window, road, adjacency, or patch constraints.
- Strict hill-climb only; no annealing or population search.
- Final-account level targets only; the existing optimizer's account-overlay search is unchanged.

## Next

Add treatment-window semantics or wire this optimization result into an estate run. The
landscape-scale WS4-vs-LBSE comparison remains blocked without an R/SpaDES reference run or
published numeric landscape output.

## Pull request

PR: #1154 is queued for maintainer approval. Do not merge without approval.
