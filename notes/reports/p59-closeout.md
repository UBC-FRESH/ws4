# Phase close-out report: P59 LiDAR in the web UI

Phase: P59, LiDAR in the web UI
Parent issue: #417
Pull request: this P59 PR
Status: queued for approval. Not merged.
Date: 2026-10-26

## Recommendation

1. Squash-merge the P59 pull request and delete `feature/p59-lidar-ui`.
2. Close tasks #418/#419/#420 and parent #417.
3. Accept the one-block validation boundary recorded below; a wide LiDAR dataset can be added
   without changing the API or UI contract.

Settings changes: none.

## Acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Registered dataset shows pin, CRS, licence, products, and fields. | TFL 6 bundle `lidarbc-995fb1f771f4d7fe`, version `2026.10.0-tfl6-pilot`, OGL-BC, EPSG:3005; five products; six block fields. | Met |
| No-LiDAR dataset shows an explicit unavailable state. | c5 `/api/lidar` returns `available: false`; browser status `this dataset has no registered LiDAR fields`, selector disabled. | Met |
| Selected fields colour blocks and appear in block detail. | Browser smoke selected `lidar_slope_mean`, observed two `lidar=1` map requests, a visible legend, and slope/CHM values in the block detail. | Met |
| Overwrite leaves one canonical column per field. | P52 integration test reproduces `_x`/`_y` columns, overwrites, and asserts no suffixed LiDAR columns remain. | Met |
| TFL 6 validation dataset and c5 fallback exercised. | Real 7-fragment / 1-block validation dataset re-integrated with canonical fields; c5 checked separately. | Met |
| Dashboard green. | Green at the report commit. | Met |

## Real-data evidence

Dataset: P52 TFL 6 validation AOI, seven VRI fragments dissolved to one 100.0 ha block.

- bundle: `lidarbc-995fb1f771f4d7fe`
- version: `2026.10.0-tfl6-pilot`
- CRS: `EPSG:3005`
- licence: OGL-BC
- fields: slope valid pixels/mean/p95 and CHM valid pixels/mean/p95
- block values: slope mean 23.95%, CHM mean 8.62 m, CHM p95 21.78 m

API: `/api/lidar` returns the pin and six canonical fields; `/api/runs/reference/map?...&lidar=1`
returns the same six values on the block feature by `block_id`.

Browser: `scripts/check_lidar_browser.py` opens the LiDAR tab, selects Slope mean, switches to the
SVG map, clicks the block, and finds the LiDAR values in the detail. The check exits 0.
The screenshot is `/tmp/opencode/p59-lidar.png` (working evidence, not committed).

c5: `/api/lidar` returns `available: false`; the tab shows the explicit unavailable message and
the selector is disabled. The normal c5 map is unchanged.

## Findings and deviations

- **P52 overwrite bug repaired.** Re-integrating over existing fields produced `_x`/`_y` copies
  because pandas suffixed both sides. P59 drops every canonical or suffixed variant before the
  join and adds a regression test. The validation dataset now has exactly six canonical fields.
- **One block only.** The real validation AOI is a single 100 ha block. It proves the contract,
  provenance, join, rendering, and detail path, not a wide-area performance claim. The LiDAR layer
  uses the existing GeoJSON map path and is intentionally disabled for MVT.
- **No raster overlay.** The UI reads block zonal summaries; it does not serve or reproject the
  source rasters. Raw terrain/canopy raster viewing remains out of scope.
- **Carbon UI is separate.** `carbon.*` accounts already appear in Accounts, Targets, and Reports.
  Carbon pool/flux charts and GCBM comparison are proposed P60, not P59.
