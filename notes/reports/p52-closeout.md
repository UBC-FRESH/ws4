# P52 Close-Out: Consume FEMIC-Compiled LidarBC Products

Phase: P52 / `#317`
Branch: `feature/p52-lidar-products`
Status: complete; PR #381 squash-merged as `bd3bc18`
Upstream producer: FEMIC P79 (`UBC-FRESH/femic#211`)

## Outcome

WS4 now consumes versioned FEMIC LidarBC product bundles without reimplementing
discovery or materialization:

- pins bundle id/version and manifest/product checksums;
- validates OGL-BC, CRS, native resolution, vertical datum, and source tiles;
- registers the pin in the compiled dataset manifest and sidecar;
- maps native slope/CHM and optional canopy/tree/VRI evidence to fragment and
  dissolved-block support;
- writes optional prefixed LiDAR fields into the compiled Parquet tables;
- preserves backward compatibility for datasets without LiDAR fields.

## End-To-End Validation

Bundle:

- `bundle_id`: `lidarbc-995fb1f771f4d7fe`
- `bundle_version`: `2026.10.0-tfl6-pilot`
- products: `dem`, `dsm`, `slope`, `chm`, `canopy`
- CRS: `EPSG:3005`; native resolution 1 m; licence OGL-BC.

AOI support:

- 7 TFL 6 VRI polygons as fragments;
- 1 dissolved block;
- 100.0 ha total.

Path exercised:

1. `ws4 lidar register` against the shared bundle.
2. `ws4 lidar map` for slope/CHM mean and p95.
3. `ws4 lidar integrate` into `fragments.parquet`/`blocks.parquet`.
4. `ws4 validate` returned valid.
5. `Simulator.from_dataset` loaded the expanded dataset with 7 fragments.

Parity:

- WS4 vs FEMIC producer reference: maximum absolute difference `7.1e-15`
  (floating-point noise; tolerance `1e-9`).
- WS4 vs FHOPS P14.1 consumer: maximum absolute difference `0.0`.

## Performance And Storage

- Map 7 fragments: `0.755 s`.
- Integrate fields: `0.037 s`.
- 50,000-fragment / 5,000-block synthetic integration benchmark: `0.143 s`.
- Bundle: 13,406,981 bytes.
- Mapping outputs: 4,374 bytes.
- Compiled validation dataset: 52,150 bytes.
- No simulator/optimizer code-path changes.

## Licence And Attribution

- Source licence: OGL-BC, carried from the FEMIC bundle manifest.
- Source: LidarBC Open LiDAR Data Portal.
- Bundle pin and product checksums are recorded in the dataset manifest.
- No full provincial mirror and no source-tile re-download.

## Verification

- 61 tests passed across LidarBC contract, CLI, schema, and simulator suites.
- Targeted `ruff` and strict mypy passed.
- Sphinx `-W` passed.
- `scripts/check_workflow.py` passed.
- Real AOI validation metrics: `notes/reports/p52-validation.json`.

## Limitations

- One 7-polygon/1-block TFL 6 AOI, not a province-wide or TFL 6-wide validation.
- LiDAR fields are available to simulation/optimization but no new model
  semantics or operability constraints were introduced in P52.
- No field-accuracy claim; CHM/VRI uncertainty remains explicit.
- No production dataset switch, release, or tag.
- FHOPS P14.1 consumer contract was used for parity; FHOPS scenario integration
  continues in P14.2/P14.3.

## Recommendation

Close P52 and continue the parallel FHOPS P14.2/P14.3 work. Any WS4 model
semantics change that consumes LiDAR fields should be a new, evidence-backed
phase rather than an implicit side effect of P52.
