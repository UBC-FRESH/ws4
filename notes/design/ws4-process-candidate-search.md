# Process candidate search

Status: implemented (P192)
Phase: P192 (#1135)
Date: 2026-11-13
Related: `notes/design/ws4-process-objective.md`, `ws4/opt/process_search.py`

## 1. Purpose

P190 evaluates one schedule through the process engine; P191 prices its final accounts. P192
evaluates a supplied set of candidate schedules and ranks them. It is the bridge between the
process evaluator and a future metaheuristic search.

It is an exhaustive candidate evaluator, not a neighbourhood search.

## 2. Search contract

Each `ProcessSearchCandidate` has:

- a non-empty, unique candidate id;
- a block-to-treatment schedule.

Every candidate uses the same seed and block mapping. Differences therefore come from the
schedules, not from the random tape. This is a common-random-numbers design.

A search needs at least one candidate and at least one target. Empty searches, duplicate ids,
negative seeds, and candidate evaluations without an objective fail loudly.

## 3. Ranking

Candidates are ranked by:

1. objective ascending;
2. candidate id ascending on ties.

`results` keeps input order; `ranking` is sorted; `best` is the first ranking entry.

## 4. Artifact

`ProcessSearchResult.write` emits:

- `process_candidate_ranking.csv`;
- `process_candidate_search.json`.

The summary records the search seed, horizon, target accounts, candidate count, best candidate,
best objective, and one ranked row per candidate with terms, harvest area, and final biomass.

## 5. Exact test values

The 3 × 3 grid, one-year horizon, and a `harvest.area_ha_total` minimum of 20 ha produce:

- full block 1 harvest (two fragments, 20 ha): objective **0.0**;
- one-fragment harvest (10 ha): objective **10.0**;
- no harvest (0 ha): objective **20.0**.

Ranking: full, one, none. Equal objectives break ties by candidate id.

## 6. Limits

- No neighbourhood moves, annealing, or population search over process runs.
- The existing optimizer's account-overlay search is unchanged.
- Final-account level targets only.
- The volume bridge and harvest semantics remain provisional.
