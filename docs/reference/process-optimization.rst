End-to-end process optimization
===============================

Purpose
-------

``ws4.opt.process_optimization`` closes the process search loop. It runs the P193 hill-climb with
a P194 grammar and returns the best process evaluation plus the search trace.

It remains a bounded process search, not the estate optimizer's account-overlay search.

Contract
--------

The grammar horizon must match the evaluation horizon, and the initial candidate must be inside
the grammar universe. The search needs at least one target.

``ScheduleMoveGrammar`` has an optional ``allow_offset_moves`` flag. When true, each existing
event can move to another unused offset on its block. The default remains add/remove only, so the
P194 neighbour counts are unchanged.

Artifact
--------

``ProcessOptimizationResult.write`` emits:

- ``process_optimization.json``;
- the P193 search history and summary;
- ``best_evaluation/`` with the P190 evaluation artifact.

Reference case
--------------

On a 3 × 3 grid with a 20 ha harvest target, the search reaches the full block-1 harvest with
objective 0, then stops on a tied candidate without moving the incumbent.

Estate handoff
--------------

``ProcessOptimizationResult.write_estate_inputs`` writes the best schedule as
``schedule.csv`` (``block_id,treatment,offset``) and the block mapping as
``block_fragments.csv`` (``block_id,fragment_id``), plus the P195 artifacts and
``best_evaluation/``.

Rows are sorted and the headers are stable. ``load_schedule`` and ``load_block_fragments``
round-trip the exported files exactly. This is an export, not an estate simulation.

Limits
------

- Caller-supplied block universe and treatments.
- No treatment-window, road, adjacency, or patch constraints.
- Strict hill-climb only.
- The existing optimizer's account-overlay search is unchanged.
