# End-to-end process optimization

Status: implemented (P195)
Phase: P195 (#1150)
Date: 2026-11-14
Related: `notes/design/ws4-process-neighbourhood.md`,
`notes/design/ws4-schedule-grammar.md`

## 1. Purpose

P190 evaluates a schedule, P191 prices it, P192 ranks candidates, P193 climbs, and P194 supplies
moves. P195 closes the loop with one API: grammar plus hill-climb plus the best process
evaluation and its artifacts.

It remains a bounded process search, not the estate optimizer's account-overlay search.

## 2. Offset moves

`ScheduleMoveGrammar` now has an optional `allow_offset_moves` flag. When true, each existing
event is moved to every other unused offset on its block. The default remains false, so the P194
add/remove neighbour counts are unchanged.

Offset moves are deduplicated with add/remove neighbours by canonical schedule id.

## 3. Optimization wrapper

`optimize_process_schedule` requires:

- a grammar whose horizon equals the evaluation horizon;
- an initial candidate inside the grammar universe;
- at least one target, inherited from the P193 search.

It runs the P193 hill-climb with `grammar.neighbours` and returns
`ProcessOptimizationResult`.

## 4. Result and artifact

`ProcessOptimizationResult` exposes:

- the full search result;
- the best evaluation;
- a JSON summary with best candidate, best objective, schedule, and accounts.

`write` emits:

- `process_optimization.json`;
- the P193 search history and summary;
- `best_evaluation/` with the P190 evaluation artifact.

## 5. Exact test values

The 3 × 3 grid, one-year horizon, and 20 ha harvest target reach the full block-1 harvest with
objective 0. The second round finds a tied objective-0 candidate and stops without moving the
incumbent.

Offset moves on `{1: (CC, 0), (CC, 1)}` with a three-year horizon add two move neighbours,
`{1: (CC, 1), (CC, 2)}` and `{1: (CC, 0), (CC, 2)}`, on top of the default add/remove set.

## 6. Limits

- The caller still supplies the block universe and treatments.
- No treatment-window, road, adjacency, or patch constraints.
- Strict hill-climb only; no annealing or population search.
- Final-account level targets only; the existing optimizer is unchanged.
