Process candidate search
========================

Purpose
-------

``ws4.opt.process_search`` evaluates a supplied set of candidate schedules through the P190
process evaluator and ranks them with the P191 objective adapter. It is the bridge to a future
metaheuristic over process runs, not a replacement for the existing optimizer.

Contract
--------

Each candidate has a unique non-empty id and a block schedule. Every candidate uses the same
seed and block mapping, so differences come from the schedule rather than the random tape.

A search needs at least one candidate and at least one target. Candidates rank by objective,
then by candidate id on ties.

Artifact
--------

``ProcessSearchResult.write`` emits:

- ``process_candidate_ranking.csv``;
- ``process_candidate_search.json``.

The summary records seed, horizon, target accounts, candidate count, best candidate and
objective, and ranked rows with terms, harvest area, and final biomass.

Reference case
--------------

On a 3 × 3 grid with a 20 ha harvest target:

- full block harvest: objective 0;
- one-fragment harvest: objective 10;
- no harvest: objective 20.

Ranking: full, one, none.

Bounded neighbourhood search
----------------------------

``search_process_neighbourhood`` adds a deterministic strict-improvement loop. The caller
supplies a neighbour function; the search evaluates unseen neighbours through the P192 ranking,
keeps only strict improvements, and stops at ``max_iterations`` or a non-improving round.

Seen candidates are skipped, duplicate ids within one round are rejected, and ties do not move
the incumbent. The result records one history step per completed round and can write a history
CSV plus a JSON summary.

Limits
------

- The caller supplies the neighbour function; no schedule mutation grammar is built in.
- Strict hill-climb only; no annealing or population search.
- The existing optimizer's account overlay is unchanged.
- Final-account level targets only.
- Harvest and volume semantics remain provisional.
