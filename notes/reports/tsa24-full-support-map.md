# TSA24 full support map

The full TSA24 single-valued 250 m raster does not work: 458,708 blocks project onto only
260,144 distinct fragment cells, leaving 198,564 blocks without a cell. The missing blocks are
not a small edge case; they are 43% of the inventory.

A nearest-empty fallback is also not acceptable. On the full extent its displacement was about
1.6 km at the median, 4.0 km at p90, and 13.3 km at the maximum. That is not a spatial
representation of a 250 m block.

## Area-weighted support

The support representation now allows one raster cell to belong to several fragments:

- 1,111,565 direct cells
- 198,564 missing fragments assigned to their representative cell
- 1,310,129 fragment memberships
- all 458,708 fragments represented
- 180,074 cells with more than one fragment
- at most 7 fragments in one cell
- per-cell weights normalized to one cell area

Each membership carries a share of the 6.25 ha cell. A burned cell now contributes its area to
every member fragment, weighted by that share, instead of dropping all but one block.

## Code

`FragmentSupport` is a validated membership grid. `fragment_ignition_times` and
`build_growth_fire_source` accept either a single-valued fragment raster or a support grid. The
single-valued path is unchanged.

The full TSA24 support map was built from the public block geometry and compiled fragment table.
It is a support map, not a completed fire run.

## Boundary

The support map uses 250 m cells and is not yet wired into a full TSA24 growth run with
complete TSA24 fuel and terrain layers. The small-block weights are cell shares; they do not
replace observed block geometry inside a cell.
