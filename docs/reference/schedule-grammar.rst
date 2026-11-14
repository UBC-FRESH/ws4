Deterministic schedule mutation grammar
=======================================

Purpose
-------

``ws4.opt.schedule_grammar`` supplies a neighbour function for the P193 process neighbourhood
search. It performs add and remove moves over a fixed block universe, treatment set, and horizon.

Universe
--------

A grammar has unique positive block ids, unique non-empty treatment names, a positive horizon,
and a positive per-block event cap. A candidate schedule is valid only when every entry is in
that universe and no block has duplicate events.

Moves
-----

For each block below its cap, the grammar adds every treatment at every unused offset. It also
removes each existing event. Add moves come first, then removes. Neighbours are deduplicated by
canonical schedule id.

Candidate ids are SHA-256 digests of the canonical schedule payload, so the same schedule always
has the same id.

Reference case
--------------

With blocks 1 and 2, treatment ``CC``, a two-year horizon, and a cap of one, the empty schedule
has four add neighbours: ``{1: (CC, 0)}``, ``{1: (CC, 1)}``, ``{2: (CC, 0)}``,
``{2: (CC, 1)}``. It has no remove neighbours.

With a cap of two and schedule ``{1: (CC, 0)}``, the neighbours are:

- ``{1: (CC, 0), (CC, 1)}``;
- ``{1: (CC, 0), 2: (CC, 0)}``;
- ``{1: (CC, 0), 2: (CC, 1)}``;
- the empty schedule.

Limits
------

- Add/remove only; no treatment-window or offset-move grammar.
- No spatial, road, adjacency, or patch constraints.
- The optimizer's existing schedule semantics are unchanged.
