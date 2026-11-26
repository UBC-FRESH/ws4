# General support-map builder

This is the reproducible method for compiling a 250 m support map from public block polygons.
It is intended for other TSAs. It does **not** reproduce the legacy TSA24 frozen map exactly; that
map remains a frozen input until its original builder is recovered.

## Inputs

- A block polygon layer with:
  - a unique integer block ID;
  - a positive area in hectares;
  - polygon geometry in a projected CRS.
- Grid parameters:
  - cell size (default 250 m);
  - optional north-west origin `(origin_x, origin_y)`;
  - optional `rows` and `cols`.

If the grid parameters are omitted, the builder uses the block bounds and snaps the origin to the
cell size.

## Method

1. Build the 250 m grid.
2. Assign every block to every cell whose centre lies inside the block.
3. If a block has no cell centre, assign its representative point to the containing cell.
4. For each cell, compute each member's share as
   `block_area / sum(block_area of all members in that cell)`.
5. Write `rows`, `cols`, `cell_index`, `fragment_id`, and `weight`.

The weights sum to one per cell. Every input block is represented.

## Command

```bash
python scripts/build_support_map.py \
  --blocks /path/to/tsaXX-blocks.geojson \
  --output results/support-map-tsaXX.npz \
  --summary results/support-map-tsaXX-summary.json \
  --cell-size 250
```

Optional grid controls:

```bash
  --origin-x 834450 --origin-y 1367370 --rows 1957 --cols 2237
```

Field overrides:

```bash
  --block-id BLOCK_ID --area AREA_HA
```

## Validation

The builder checks:

- unique block IDs;
- every block is represented;
- every cell has positive total block area, or equal shares if all members have zero area;
- every cell's weights sum to one.

## TSA24 comparison

Run on the public TSA24 block GeoJSON with the canonical grid:

| Quantity | General builder | Frozen TSA24 map |
| --- | ---: | ---: |
| Blocks | 458,708 | 458,708 |
| Cells | 960,506 | 1,111,565 |
| Memberships | 1,053,254 | 1,310,129 |
| Multi-fragment cells | 85,152 | 180,074 |
| Max fragments per cell | 7 | 7 |

The builder is a defensible general method, but it is **not** a replacement for the frozen TSA24
support map. The difference is recorded rather than hidden; the legacy map remains canonical for
the current paper.

## For another TSA

1. Obtain the public block geometry for the TSA.
2. Choose the grid origin and extent.
3. Run the command above.
4. Validate all blocks are represented and all cell weights sum to one.
5. Store the builder commit, input hash, output hash, and summary alongside the map.
