# FEMIC LidarBC Consumer Contract (P52.1)

WS4 consumes FEMIC P79 product bundles. It does not discover LidarBC tiles,
download source products, or reimplement terrain/canopy processing.

## Bundle Pin

WS4 records:

- `bundle_id`
- `bundle_version`
- `manifest_sha256`
- every product `sha256` and `relative_path`

The loader is `ws4.io.lidar.load_femic_lidar_bundle`. It validates:

- manifest schema `femic.lidar.product.v1`;
- layout `femic.lidar.bundle.v1`;
- bundle identity and optional expected pin;
- OGL-BC licence;
- source native CRS;
- per-product CRS, resolution, vertical datum, source-tile membership;
- path containment, file size, and SHA-256.

## Support Mapping

`summarize_femic_lidar_for_polygons` maps a bundle raster to polygon support.
Polygon CRS must already match the product CRS. The function uses `mean`,
`p95`, `min`, or `max` and never reprojects or resamples.

WS4 uses polygon means for fragment/block support and p95 for block-level steep
or canopy summaries. The aggregation footprint must be recorded by the caller.

## Optional Dependencies

The manifest/checksum validator is stdlib-only. Polygon summaries require
`ws4[lidar]` (`geopandas`, `pyogrio`, `rasterio`).

## Registration

`register_femic_lidar_bundle(dataset_dir, bundle_dir)` validates the bundle and
writes the pin to two places:

- dataset `manifest.json` → `metadata.lidar_products`;
- `lidar_products.json` sidecar.

The bundle is referenced, not copied. `read_registered_femic_lidar` and
`validate_registered_femic_lidar` inspect/revalidate the pin. The CLI exposes
`ws4 lidar register|inspect|validate`, and `ws4 build --lidar-bundle` registers
during a build.

## Fragment And Block Mapping

`map_femic_lidar_to_fragments` computes:

- fragment support: zonal statistics over each fragment polygon;
- block support: zonal statistics over the dissolved block geometry.

Defaults are `fragment_id`, `block_id`, `area_ha`, products `slope`/`chm`, and
statistics `mean`/`p95`. `write_lidar_mapping` writes fragment/block CSVs plus a
manifest carrying the bundle pin, product checksums, CRS, resolution, and the
aggregation rules. No resampling or reprojection is performed.

## Canopy And Precision Forestry

`map_femic_canopy_to_fragments` maps CHM mean/p90/p95/max and cover at
2/5/10 m to fragment and dissolved-block support. Optional VRI overlap adds
area-weighted height/closure, CHM-minus-VRI deltas, and uncertainty summaries.
Optional bundle tree products add tree counts, height mean/p95, and species
counts. `write_canopy_mapping` writes CSVs plus a manifest with provenance,
aggregation rules, uncertainty, and caveats.

## Dataset Integration

`integrate_lidar_mapping_into_dataset` joins mapping CSVs to the compiled
fragment/block Parquet tables, prefixing fields with `lidar_`. The manifest
under `metadata.lidar_fields` records the bundle pin, mapping hashes, field
lists, support keys, and integration timestamp. Fields are optional; datasets
without them remain valid and the simulator loads the expanded tables unchanged.
Re-integration requires `overwrite=True` (`--overwrite`).

## Shared Parity

Validated against FEMIC bundle `lidarbc-995fb1f771f4d7fe`
(`2026.10.0-tfl6-pilot`) over seven TFL 6 AOI polygons. WS4 and FHOPS values
matched exactly (max absolute difference 0.0) for slope/CHM mean and p95.
