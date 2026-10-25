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

## Shared Parity

Validated against FEMIC bundle `lidarbc-995fb1f771f4d7fe`
(`2026.10.0-tfl6-pilot`) over seven TFL 6 AOI polygons. WS4 and FHOPS values
matched exactly (max absolute difference 0.0) for slope/CHM mean and p95.
