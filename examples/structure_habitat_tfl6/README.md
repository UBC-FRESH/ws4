# TFL 6 structure habitat index

Real-data pilot for the published Coops et al. (2016) structure habitat index.
The two public LidarBC 2024 LAZ tiles over the TFL 6 1 km AOI were downloaded and
processed; the seven VRI polygons are the blocks.

## Source

- LidarBC point cloud index, FeatureServer layer 4.
- Contract: `OP24BMRS001`, acquisition 2024, 8 points/m², UTM zone 9, CGVD2013.
- LAZ tiles:
  - `bc_092l062_2_3_4_xyes_8_utm9_20240316_20240317.laz`
  - `bc_092l062_4_1_2_xyes_8_utm9_20240316_20240317.laz`
- Licence: OGL-BC.
- Point classes present: 1, 2, 7, 12.
- Normalization: first-return height above the FEMIC 1 m DEM.
- DHI: SILVIS MODIS 6.1 Terra NDVI composite 2003-2022, 500 m subset over the
  AOI.

## Method

First returns (`return_number == 1`) inside each VRI polygon, heights normalized
with the FEMIC DEM, then:

- `height_p95_m`: 95th percentile of first-return heights;
- `cover_gt_1_37_pct`: percentage of first returns above 1.37 m;
- `complexity_sd_gt_1_37_m`: sample SD of first-return heights above 1.37 m.

This is a block-level aggregation of the published point statistics, not a
30 m cell raster product. The point counts are retained in `structure_metrics.csv`
so support is auditable.

## Results

Seven blocks, 100 ha:

- area-weighted mean height **22.95 m**;
- area-weighted mean cover **69.82%**;
- area-weighted mean complexity **6.86 m**;
- five blocks class `H2-C2-K2`, one `H1-C0-K2`, one `H2-C0-K2`;
- height: 94.78% high, 5.22% medium, 0% low;
- cover: 88.15% high, 0% medium, 11.85% low;
- complexity: 100% high.

DHI comparison on the seven blocks:

- structure height vs DHI variation: positive, strong rank agreement
  (Spearman +0.67);
- structure cover vs DHI variation: positive, strong (Spearman +0.80);
- most other component/band pairs are weak or negative. With seven blocks and
  repeated 500 m DHI pixels this is exploratory, not evidence of a general
  relationship.

## Commands

```bash
# DHI ingest uses feature_id because the VRI file has no block_id column.
ws4 dhi ingest \
  --raster /path/to/tfl6_dhi.tif \
  --blocks .../runtime/dem/p79_7_canopy_pilot/vri_aoi.geojson \
  --block-id-field feature_id \
  --output examples/structure_habitat_tfl6/dhi_values.csv \
  --metadata examples/structure_habitat_tfl6/dhi_metadata.json \
  --source-version "MODIS 6.1 Terra NDVI Composite RGB (2003-2022)"

ws4 shi ingest \
  --metrics examples/structure_habitat_tfl6/structure_metrics.csv \
  --output examples/structure_habitat_tfl6/structure_habitat_stand.csv \
  --metadata examples/structure_habitat_tfl6/structure_habitat_metadata.json \
  --source-id lidarbc-tfl6-op24bmrs001 \
  --source-version "OP24BMRS001 / 2024 LAZ / 8 ppm2"

ws4 shi compare \
  --structure examples/structure_habitat_tfl6/structure_habitat_stand.csv \
  --dhi-values examples/structure_habitat_tfl6/dhi_values.csv \
  --output examples/structure_habitat_tfl6/dhi_comparison.csv
```

## Caveats

- Two VRI blocks have very low first-return cover (11.5% and 14.8%) despite tall
  P95 heights; they are retained rather than smoothed away.
- The point-class list lacks a high-vegetation class, so the first-return
  threshold can include non-canopy returns. The AOI is forest VRI, but this is a
  data-quality limit.
- The DHI comparison uses seven blocks and repeated 500 m pixels.
- This is a real pilot, not a species-habitat validation.
