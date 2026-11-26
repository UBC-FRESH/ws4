# Support-map builder

Date: 2026-11-26
Status: canonical method in the archive

## Decision

The canonical TSA24 support map is the positive-overlap, cell-share map produced by
`scripts/build_support_map.py`. The legacy frozen map is retained only for sensitivity. This
replaces the earlier centre-based candidate, which dropped sliver overlaps and changed the estate
case without a geometric justification.

## Method

1. Build the 250 m grid.
2. Intersect every block with every cell.
3. Keep every positive intersection.
4. Set `weight = intersection_area / cell_area`.
5. If overlapping block polygons make a cell's shares sum above one, scale that cell down to one.
6. Represent degenerate zero-area blocks at their representative point, with a negligible weight.

Per-cell weights therefore sum to at most one. A block's represented area is
`sum(weight * cell_area)`.

## TSA24 result

| Quantity | Canonical area-overlap | Legacy frozen |
| --- | ---: | ---: |
| Blocks | 458,708 | 458,708 |
| Cells | 1,116,185 | 1,111,565 |
| Memberships | 3,546,374 | 1,310,129 |
| Multi-fragment cells | 979,160 | 180,074 |
| Max fragments per cell | 16 | 7 |
| Blocks within 20% area | 99.7% | 9.6% |
| Median block-area error | 0.4% | 64.1% |

The legacy map assigns some blocks to cells with no overlap and has a median block-area error of
64%. It is not defensible as an area representation.

## Does it change the paper?

- Calibration, temporal, and transfer results: no, they use the potential fires and layer tiles.
- Estate: 5,842.3 to 6,360.7 ha burned; 565 to 728 events.
- Risk median: 7,478.8 to 10,822.6 ha; worst-of-five loss 1.384 to 2.069 million m3.
- Optimizer: 112 to 113 tiles, 661.0 to 2,075.9 ha burned; schedule remains fire-blind invariant.

## Verification and portability

- An independent verifier re-reads the archived map and block polygons; it checks memberships, cell
  range, duplicate pairs, cell-weight caps, block coverage, and block-area error. A deliberately
  corrupted copy is rejected with `cell weights exceed one`.
- The same builder compiled the public TSA27 block layer: 37,461 blocks, 89,139 cells, 259,758
  memberships, all blocks represented, no cell above one. The TSA27 map is not archived; its
  summary and validation are.
- TSA27 input SHA-256: `e49364cb97b72e1559452142bd6d6a6fd0f04b47b4c5ebb95d498f9847740178`.
- TSA27 has no area field, so its area agreement is algebraic by construction; coverage, cell caps,
  and representation are the meaningful checks.
- Canonical builder commit: `7f86f9e`; canonical map SHA-256:
  `f47b36eb75a80709a0c2a289671487ef9348bfd0720b162dc52d5e1ddb5c41f4`.

## Remaining check

The earlier 10-event reconstruction used the legacy map and is not canonical evidence. A fresh
event reconstruction under the canonical map is optional; the paper now rests its temporal claim on
the distributional holdout, which does not use the support map.
