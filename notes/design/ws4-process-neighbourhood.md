# Bounded process neighbourhood search

Status: implemented (P193)
Phase: P193 (#1140)
Date: 2026-11-13
Related: `notes/design/ws4-process-candidate-search.md`

## 1. Purpose

P192 ranks a supplied candidate set. P193 adds a deterministic hill-climb: the caller supplies
a neighbour function, unseen neighbours are evaluated through P192, and the search keeps only
strict improvements.

The caller owns the schedule mutation grammar. The search does not invent treatment semantics.

## 2. Algorithm

1. Evaluate the initial candidate.
2. For each round up to `max_iterations`:
   - ask the neighbour function for candidates;
   - drop candidates already seen;
   - reject duplicate ids within one round;
   - evaluate the unseen neighbours with the common seed;
   - choose the best neighbour by objective and id;
   - stop unless it strictly improves the incumbent;
   - otherwise make it the new incumbent.
3. Return the best evaluation, round history, and every evaluation.

A tie does not move the incumbent. Empty, fully-seen, or non-improving neighbourhoods stop the
search.

## 3. History and artifact

`ProcessNeighbourhoodResult` records one step per completed round:

- iteration;
- selected candidate id;
- objective;
- strict-improvement flag;
- number of unseen neighbours evaluated.

`write` emits:

- `process_neighbourhood_history.csv`;
- `process_neighbourhood_search.json`.

The JSON summary records the seed, horizon, bound, iterations, initial candidate, best
candidate and objective, target accounts, evaluated candidate ids, and history rows.

## 4. Exact test values

The 3 × 3 grid, one-year horizon, and a 20 ha harvest target give:

- no harvest: objective 20;
- one fragment: objective 10;
- full block harvest: objective 0.

The improving chain `none → one → full` takes two rounds and reaches objective 0. A one-round
bound stops at `one` with objective 10. A non-improving neighbour leaves the incumbent
unchanged.

## 5. Limits

- The caller supplies neighbours; there is no built-in schedule mutation grammar.
- Strict hill-climb only, not annealing or a population method.
- The existing optimizer's account-overlay search is unchanged.
- Final-account level targets only.
