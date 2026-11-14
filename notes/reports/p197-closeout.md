# P197 close-out: per-block treatment windows

Date: 2026-11-14
Phase: P197 (#1160)
Branch: `feature/p197-treatment-windows`
Tasks: P197.1 (#1161), P197.2 (#1162), P197.3 (#1163)
Design note: `notes/design/ws4-treatment-windows.md`

## Result

The schedule grammar now supports optional per-block treatment windows. Adds, offset moves, and
schedule validation respect the window; blocks without a window keep the full horizon.

## What changed

- `ScheduleMoveGrammar.windows`: block to inclusive/exclusive offset range.
- Window-aware add and offset-move generation.
- Window-aware validation.
- Exact window, invalid-window, default-preservation, and windowed-optimization tests.
- Reference documentation.

## Evidence

- Grammar tests: 9 passed.
- Optimization tests: 7 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Blocks 1 and 2, four-year horizon, cap one, window `{1: (1, 3)}`:
  - six add neighbours: block 1 at 1/2; block 2 at 0/1/2/3;
  - block-1 offset 0 or 3 fails validation.
- Windowed two-year optimization with `{1: (1, 2)}` and a 20 ha target selects
  `{1: (CC, 1)}` with objective 0.

## Boundary

- No age-based eligibility or treatment-specific windows.
- No road, adjacency, patch, or spatial constraints.
- The caller supplies blocks and treatments.
- The existing optimizer's schedule semantics are unchanged.

## Next

Attempt the open-source SpaDES/LandR reference run rather than treating it as blocked. That work
needs an isolated R library, the LandR/SpaDES dependency set, and a pinned Biomass_core case.

## Pull request

Merged as `1918bdf` (PR #1172); branch deleted.
