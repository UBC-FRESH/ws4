# TSA24 support map provenance

Status: frozen input, not reproducible from the current repository
Date: 2026-11-26

## Artifact

- Path: `manifests/tsa24-full-250m-support.npz`
- SHA-256: `00b02af99ac43aa365f3e43a86b75de6df695da11ff3828c6d48718ef9399b85`
- Shape: 1,957 x 2,237 cells at 250 m
- Blocks: 458,708
- Memberships: 1,310,129
- Unique support cells: 1,111,565
- Multi-fragment cells: 180,074
- Maximum fragments per cell: 7

## What is known

The support map was built once from the public TSA24 block geometry and the compiled fragment
table. It is an area-weighted membership grid: each cell carries one or more fragment IDs and
per-cell weights normalized to one cell area.

The block geometry is now available locally:

- `femic-tsa24-instance/data/shp/tsa24.shp/stands.{shp,shx,dbf}` (recovered from annex copies)
- `femic-tsa24-instance/runtime/geometry/tsa24-blocks.geojson` (458,708 features with `block_id`,
  `area_ha`, `age`, `au`)

## What is missing

The builder script and the exact block-to-cell assignment rule are **not committed** in the
archive or in the current WS4 git history. The report describing the map is
`notes/reports/tsa24-full-support-map.md`; it describes the intended representation but not the
code.

A simple reconstruction from the current block GeoJSON does not match the frozen map. For test
blocks, a cell-centre rule gives different cell sets and weights. The likely causes are a different
block-geometry version, a different rasterization rule, or both. No reconstruction has been
accepted as exact.

## Reproducibility boundary

For the current paper and archive:

- Clean-host runs start from this **frozen, hashed support map**.
- Do not claim the support map is derived from raw block geometry in the repository.
- Do not replace this file with an approximate reconstruction without matching the counts,
  memberships, and weights above.
- If a future builder is recovered, add its hash and a comparison report before changing the
  canonical artifact.

This is a provenance gap, not missing data.
