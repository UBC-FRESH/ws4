# P193 close-out: bounded process neighbourhood search

Date: 2026-11-13
Phase: P193 (#1140)
Branch: `feature/p193-process-neighbourhood`
Tasks: P193.1 (#1141), P193.2 (#1142), P193.3 (#1143)
Design note: `notes/design/ws4-process-neighbourhood.md`

## Result

A deterministic strict-improvement hill-climb now runs over process-conditioned schedule
candidates. The caller supplies the neighbour function; unseen neighbours are evaluated through
P192 with a common seed, and the search stops at the iteration bound or a non-improving round.

The caller owns the schedule mutation grammar.

## What changed

- `ws4/opt/process_neighbourhood.py`:
  - `ProcessNeighbourhoodStep`, `ProcessNeighbourhoodResult`;
  - bounded strict-improvement search;
  - seen-candidate skipping and duplicate-id rejection;
  - history CSV and JSON summary.
- Tests for improvement, bound, stopping, seen/empty neighbourhoods, artifacts, and invalid
  inputs.
- Reference section and design note.

## Evidence

- Neighbourhood tests: 6 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- 3 × 3 grid, 20 ha harvest target:
  - no harvest: objective 20;
  - one fragment: objective 10;
  - full block harvest: objective 0.
- The chain `none → one → full` takes two rounds and reaches objective 0.
- A one-round bound stops at `one` with objective 10.
- A non-improving neighbour leaves the incumbent unchanged.

## Boundary

- Caller-supplied neighbours; no built-in schedule mutation grammar.
- Strict hill-climb only, not annealing or a population method.
- The existing optimizer's account-overlay search is unchanged.
- Final-account level targets only.
- Harvest and volume semantics remain provisional.

## Next

Add a small built-in mutation grammar, or wire the neighbourhood search into an optimizer
mode. The landscape-scale WS4-vs-LBSE comparison remains blocked without an R/SpaDES reference
run or published numeric landscape output.

## Pull request

PR: #1144 is queued for maintainer approval. Do not merge without approval.
