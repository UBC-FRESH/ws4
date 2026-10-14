# System functional test

A full end-to-end check over a complete model: ingest, validate, simulate, optimize,
report, and route. The model is the sample dataset shipped with the installer
(`app/sample/`), which has blocks, roads, mills, a compiled matrix, and a PIN file.

## Inputs (extracted from the installer, not committed)

- `tracks/` — the compiled matrix (`tracknames`, `strata`, `treatments`, `blocks`,
  `features`, `curves`, `products`, `accounts`, `groups`, `messages`).
- `blocks/blocks.shp` + `topology_blocks_200r.csv` — the block geometry and topology.
- `roads/` — `vertices`, `segments`, `destinations`, `linkages`, `mill.shp`, and haul costs.
- `analysis/C5_2018.pin` — the launch control file.

The sample is unpacked from the installer into a working directory outside the repository
(`tmp/`). Nothing from it is committed.

## Procedure

```python
# 1. Fragments: one per compiled block portion (BLOCK, AREA_HA, F_AGE).
# 2. Ingest the matrix into the WS4 schema.
dataset = ingest_legacy_matrix("tracks", "fragments.csv", "compiled")
# 3. Validate.
assert validate_dataset(dataset) == []
# 4. Simulate a schedule.
Simulator.from_dataset(dataset).run("schedule.csv", years=30, out_dir="run")
# 5. Optimize against a target.
Optimizer.from_dataset(dataset, cfg).run("run")
# 6. Report.
write_report(values, targets, "run")
# 7. Route a block to a destination.
network = RouteNetwork.from_tables(segments, destinations, linkages)
network.nearest_destination(block_id)
```

## Result (recorded)

- Ingest: `tracks 1558`, `strata 3551`, `treatments 1398`, `blocks 16174`, `features 20151`,
  `products 4940`, `accounts 52`, `groups 12567`, `fragments 16174`, `curves 130423`;
  validation reports **0 problems**.
- Simulate 30 years over 16174 fragments in about 13 seconds; 34 accounts.
- Optimize: writes `schedule.csv`, `account_values.csv`, `product_values.csv`,
  `report_accounts.csv`, `report_targets.csv`, and `summary.json`; a target on
  `feature.Area.managed.DF` at year 2 reports `met`.
- Roads: `vertices 27231`, `segments 36721`, `destinations 3`, `linkages 12567`; block 1's
  nearest destination is about 66.4 km away, and a route cost is reported.

## Notes

- The sample's road tables use `FNODE`/`TNODE`/`NODE`; the network accepts those and the
  WS4 names (`from_vertex`/`to_vertex`/`vertex_id`).
- The sample's matrix has no `fragments` table; fragments are built from the compiled
  blocks. A real dataset derives them from the blocks shapefile.
- The simulator evaluates feature curves vectorized per curve (a large model would be far
  too slow otherwise).
