# P194 close-out: deterministic schedule mutation grammar

Date: 2026-11-14
Phase: P194 (#1145)
Branch: `feature/p194-schedule-grammar`
Tasks: P194.1 (#1146), P194.2 (#1147), P194.3 (#1148)
Design note: `notes/design/ws4-schedule-grammar.md`

## Result

The P193 neighbourhood search can now run from a built-in add/remove grammar. The grammar
operates on a fixed block universe, treatment set, and horizon, and derives stable candidate
ids from the canonical schedule.

## What changed

- `ws4/opt/schedule_grammar.py`:
  - `ScheduleMoveGrammar`;
  - canonical schedule ids;
  - deterministic add/remove neighbours;
  - validation of blocks, treatments, offsets, event caps, and duplicates.
- Tests for exact neighbour sets, ids, validation, and P193 integration.
- Reference page and design note.

## Evidence

- Grammar tests: 6 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Blocks 1 and 2, treatment `CC`, two-year horizon, cap one:
  - empty schedule: four add neighbours, no removes.
- Cap two with `{1: (CC, 0)}`:
  - add offset 1 on block 1;
  - add offsets 0 and 1 on block 2;
  - remove the block-1 event.
- The grammar drives the P193 search from empty to the full block-1 harvest with objective 0,
  then stops on a tied candidate without moving the incumbent.

## Boundary

- Add/remove only; no treatment-window or offset-move grammar.
- No spatial, road, adjacency, or patch constraints.
- The caller chooses the block universe and treatments.
- The existing optimizer's schedule semantics are unchanged.

## Next

Add an offset-move or treatment-window grammar only when the estate semantics support it.
The landscape-scale WS4-vs-LBSE comparison remains blocked without an R/SpaDES reference run or
published numeric landscape output.

## Pull request

PR: #1149 is queued for maintainer approval. Do not merge without approval.
