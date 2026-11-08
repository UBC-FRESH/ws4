# WS4 Pareto solution-space explorer

Date: 2026-11-05
Phase: P136
Branch: `feature/p136-pareto-explorer`

## Goal

Make a target-weight portfolio legible as a decision surface instead of a table of
independent runs. The browser maps one metric to X, one to Y, one to Z, then adds
colour, size, opacity, and a filter. A dominance toggle decides whether the view shows
all members, the exact front, or a labelled near-front sample.

This is a port of the interaction pattern from the urban-forest lab, not a copy of its
optimizer. WS4 keeps its goal-programming objective and its exact replay contract.

## Data contract

`ws4.opt.solution_space.build_solution_space` consumes the `portfolio.json` document
already written by `scripts/portfolio.py`. It:

1. Keeps every successful member that carries all declared metrics.
2. Recomputes the nondominated front over those members with `ws4.opt.archive`.
   The schedule archive is capacity-bounded, so its front is not used for the explorer.
3. Normalizes each metric to `0 = worst`, `1 = best` using the declared direction.
4. Adds the scalar objective as an optional dimension, always minimized.
5. Computes each member's Chebyshev distance to the nearest front point in the
   normalized outcome box. A user-selected epsilon labels near-front members without
   calling them Pareto.

The front is over **outcome metrics only**. The scalar objective is an aggregate used by
the search and is available as a dimension, but it does not define dominance for the
solution surface.

`GET /api/search/{name}/space?near_front=<epsilon>` returns this payload. Member paths
are resolved under the artifact directory; paths outside it are dropped.

## Browser

The new **Pareto** workspace reads a saved portfolio artifact:

- X, Y, and Z map to any dimension.
- Colour and size map to other dimensions; opacity can map to another or stay fixed.
- A threshold filter applies to one dimension.
- Dominance is `all members`, `exact front`, or `near-front <= epsilon`.
- Drag orbits, wheel zooms, click selects, and a selected member can be pinned for a
  three-way comparison or have its schedule opened.
- Three.js and OrbitControls are vendored under `ws4/web/static/vendor/three/`; the
  view does not require a network connection.

## Limits

- The weight grid is a finite, budgeted sample. The surface is not a certified Pareto
  manifold. The Search scanner can build 5-7 target dimensions, including periodic
  `account@period` rows; high-dimensional grids should use the seeded random sample.
- Normalization is relative to the current sample, so changing the included members
  changes the visual box.
- Near-front is a display aid, not a dominance result.
## Weight scans and workers

`scripts/portfolio.py` supports `--mode grid|random`, `--max-members`, `--sample-seed`,
and `--workers`. Grid mode keeps the exact Cartesian product and refuses an oversized
one. Random mode samples distinct grid positions deterministically without materializing
the product. Workers are separate processes and each loads its own dataset; the default
is one, because memory is the limiting resource. The Search tab's scan builder writes the
`vary` expression and warns when the grid exceeds the cap.
