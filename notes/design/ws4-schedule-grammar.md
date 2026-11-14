# Deterministic schedule mutation grammar

Status: implemented (P194)
Phase: P194 (#1145)
Date: 2026-11-14
Related: `notes/design/ws4-process-neighbourhood.md`

## 1. Purpose

P193's neighbourhood search needs a neighbour function. P194 supplies a deterministic
add/remove grammar over a fixed block universe, treatment set, and horizon. It is intentionally
small: treatment windows, adjacency, roads, and patch constraints belong to the estate model.

## 2. Universe

`ScheduleMoveGrammar` takes:

- unique positive block ids;
- unique non-empty treatment names;
- a positive horizon;
- a positive per-block event cap.

A candidate schedule is valid only when every block, treatment, and offset is inside that
universe, no block exceeds the cap, and no block has duplicate events.

## 3. Moves

For each block below its event cap, the grammar adds every treatment at every unused offset.
It also removes each existing event. Add moves come first, then removes. Neighbours are
deduplicated by canonical schedule id.

Candidate ids are SHA-256 digests of the canonical schedule payload. The same schedule always
has the same id, regardless of input ordering.

## 4. Exact test values

With blocks 1 and 2, treatment `CC`, a two-year horizon, and a cap of one:

- the empty schedule has four add neighbours:
  - `{1: (CC, 0)}`, `{1: (CC, 1)}`, `{2: (CC, 0)}`, `{2: (CC, 1)}`;
- the empty schedule has no remove neighbours.

With a cap of two and schedule `{1: (CC, 0)}`, there are four neighbours:

- add `CC` at offset 1 on block 1;
- add `CC` at offsets 0 and 1 on block 2;
- remove the block-1 event, producing the empty schedule.

## 5. P193 integration

On the 3 × 3 grid with a 20 ha harvest target, the grammar starts from the empty schedule and
drives the P193 search to the full block-1 harvest with objective 0. The next round finds a
tied objective-0 candidate and stops without moving the incumbent.

## 6. Limits

- Add/remove only; no treatment-window or offset-move grammar.
- No spatial, road, adjacency, or patch constraints.
- The caller still chooses the block universe and treatments.
- The existing optimizer's schedule semantics are unchanged.
