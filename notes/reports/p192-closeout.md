# P192 close-out: process candidate search

Date: 2026-11-13
Phase: P192 (#1135)
Branch: `feature/p192-process-candidate-search`
Tasks: P192.1 (#1136), P192.2 (#1137), P192.3 (#1138)
Design note: `notes/design/ws4-process-candidate-search.md`

## Result

A supplied set of candidate schedules can now be evaluated through the process engine and
ranked by the weighted objective. Every candidate uses the same seed and block mapping, so
schedule differences are isolated from random-tape differences.

This is an exhaustive candidate evaluator, not a metaheuristic.

## What changed

- `ws4/opt/process_search.py`:
  - `ProcessSearchCandidate`, `ProcessSearchEvaluation`, `ProcessSearchResult`;
  - shared-seed evaluation through `evaluate_process_schedule`;
  - objective ranking with candidate-id tie-break;
  - ranking CSV and JSON summary.
- Tests for exact ranking, tie-break, determinism, artifacts, and invalid inputs.
- Reference page and design note.

## Evidence

- Search tests: 6 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- 3 × 3 grid, one-year horizon, 20 ha harvest target:
  - full block 1 harvest, 20 ha: objective **0.0**;
  - one fragment, 10 ha: objective **10.0**;
  - no harvest, 0 ha: objective **20.0**.
- Ranking: full, one, none.

## Boundary

- Exhaustive candidate evaluation only; no neighbourhood, annealing, or population search.
- The existing optimizer's account-overlay search is unchanged.
- Final-account level targets only.
- Harvest and volume semantics remain provisional.

## Next

Wrap the candidate evaluator in a bounded neighbourhood search, or add an optimizer mode that
uses it for a small candidate set. The landscape-scale WS4-vs-LBSE comparison remains blocked
without an R/SpaDES reference run or published numeric landscape output.

## Pull request

PR: #TBD is queued for maintainer approval. Do not merge without approval.
