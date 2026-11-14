# Per-block treatment windows

Status: implemented (P197)
Phase: P197 (#1160)
Date: 2026-11-14
Related: `notes/design/ws4-schedule-grammar.md`,
`notes/design/ws4-process-optimization.md`

## 1. Purpose

The schedule grammar previously allowed every offset in the horizon. P197 adds optional
per-block treatment windows, so add and offset-move neighbours stay inside the legal timing
range.

This is a timing constraint, not an age-eligibility model.

## 2. Contract

`ScheduleMoveGrammar.windows` maps a block id to `(start, end)` offsets:

- `start` is inclusive;
- `end` is exclusive;
- omitted blocks keep the full horizon;
- `0 <= start < end <= horizon_years`.

A candidate schedule outside its block window is invalid. Adds and offset moves iterate only
over the block's window.

## 3. Exact evidence

With blocks 1 and 2, a four-year horizon, a cap of one, and window `{1: (1, 3)}`, the empty
schedule has six add neighbours:

- block 1 at offsets 1 and 2;
- block 2 at offsets 0, 1, 2, and 3.

A block-1 event at offset 0 or 3 fails validation.

A windowed two-year optimization with `{1: (1, 2)}` and a 20 ha target selects
`{1: (CC, 1)}` with objective 0.

## 4. Defaults

The default remains no windows, so the P194/P195 add/remove/offset-move neighbour counts are
unchanged.

## 5. Limits

- No age-based eligibility or treatment-specific windows.
- No road, adjacency, patch, or spatial constraints.
- The caller still supplies the block universe and treatment set.
- The existing optimizer's schedule semantics are unchanged.
