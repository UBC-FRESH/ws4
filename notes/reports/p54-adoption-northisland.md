# P54 adoption validation: North Island

Date: 2026-10-26
Scope: post-merge validation of the P54 environmental accounts on a real
compiled estate, plus the TFL 6 structure-habitat coverage gap.
Status: validation only; no code or objective change.

## Why North Island, not TFL 6, for the estate run

The TFL 6 instance has a real LiDAR bundle and seven VRI AOI polygons, but no
compiled WS4 matrix or schedules. The North Island instance has a real compiled
matrix (51,289 blocks, 56,187 fragments), block polygons, and existing 31-year
schedules. It is therefore the better unit for an adoption run. TFL 6 remains the
evidence for the structure-habitat gap below.

## Data-quality finding first

`femic-northisland-instance/runtime/fragments.geojson` declares `EPSG:4326` but
its coordinates are BC Albers (`EPSG:3005`). Treating it as 4326 produces
out-of-range coordinates. The run below overrides the CRS to 3005 before any
reprojection to the DHI raster. This is a producer-side metadata defect worth
fixing in the instance.

## DHI coverage

- Product: SILVIS MODIS 6.1 Terra NDVI Composite RGB, 2003-2022, 500 m.
- WCS subset: longitude -128.80 to -126.10, latitude 49.85 to 51.00.
- Raster SHA-256:
  `2043ef3db202680ea5c52383ca23f9d32d387a7e1f3f1be409d2d7d1c808fed8`.
- Blocks: **51,289 / 51,289** sampled; no gaps.
- AOI area: **442,452 ha**.

DHI value distribution over blocks:

| Band | p5 | Median | p95 | Mean |
| --- | ---: | ---: | ---: | ---: |
| cumulative | 0.0118 | 0.0471 | 0.2094 | 0.0719 |
| minimum | 0.3294 | 0.7569 | 0.8824 | 0.6823 |
| variation | 0.0039 | 0.2314 | 0.7804 | 0.3076 |

The distribution is right-skewed for cumulative and variation DHI. A block-level
mean is sensitive to the many low-value blocks; the account therefore reports
both the index-hectare total and the area-weighted mean.

## Estate runs

Schedules: the existing `baseline` and `scenario_retain_low`, 31 years, replayed
with `--resilience` and the DHI account. Topology was derived from block polygons
that share a boundary: 107,095 undirected edges.

| Account | Baseline first -> final | Retain-low first -> final |
| --- | ---: | ---: |
| DHI area (ha) | 442,452 -> 381,092 | 442,452 -> 403,113 |
| DHI cumulative (index-ha) | 29,760 -> 27,003 | 29,760 -> 28,051 |
| DHI cumulative mean | 0.0673 -> 0.0709 | 0.0673 -> 0.0696 |
| DHI minimum mean | 0.6928 -> 0.6858 | 0.6928 -> 0.6871 |
| DHI variation mean | 0.3253 -> 0.3073 | 0.3253 -> 0.3120 |
| Largest untreated component (ha) | 168,572 -> 132,005 | 168,572 -> 144,527 |
| Untreated area (ha) | 442,452 -> 381,092 | 442,452 -> 403,113 |
| Age Shannon | 2.618 -> 2.692 | 2.618 -> 2.681 |
| Age evenness | 0.762 -> 0.770 | 0.762 -> 0.767 |
| Opening patches (count, total) | 1,330 | 1,288 |
| Opening area (ha, total) | 61,360 | 39,339 |

### What this says

- DHI area and total DHI fall as harvest removes blocks, but the area-weighted
  cumulative mean **rises** in the baseline run. The schedule is removing
  lower-DHI blocks on average. Total and mean therefore tell different stories;
  both are needed.
- `scenario_retain_low` keeps 22,021 ha more untreated forest than baseline and
  a larger largest component. The DHI total and connectivity are consistent with
  that retention, but they are not the same metric.
- Age Shannon is nearly unchanged across the two schedules (2.692 vs 2.681),
  while opening area and connectivity differ. Age diversity is not a restatement
  of fragmentation or retention.
- Fragmentation is a per-year flow: the total opening area is 61,360 ha baseline
  vs 39,339 ha retain-low, even though the final-year opening area and patch
  count are identical. Reporting only final offset would hide the difference.

## Structure habitat gap

The TFL 6 bundle exposes CHM-derived P95 and cover >= 2 m, not the published
first-return metrics. `ws4 shi diagnose` reports `index_computable: false` with
all three exact metrics missing and the CHM fields listed as proxies. No
structure-habitat trajectory is reported for North Island either, because that
instance has no first-return point-cloud metrics in the compiled product.

This is the adoption decision point:

1. acquire first-return point-cloud metrics for the pilot units, or
2. approve a separately named CHM proxy as a different index.

Do not present a CHM proxy as the published Coops et al. index.

## Commands

```bash
# DHI WCS subset (source raster SHA-256 shown above)
# longitude -128.80..-126.10, latitude 49.85..51.00

# Correct the North Island CRS metadata, then reproject for DHI sampling.
python - <<'PY'
import geopandas as gpd
g = gpd.read_file(
    "femic/external/femic-northisland-instance/runtime/fragments.geojson"
).set_crs(3005, allow_override=True)
g[["block_id", "geometry"]].drop_duplicates("block_id").to_crs(4326).to_file(
    "/tmp/northisland_blocks.geojson", driver="GeoJSON"
)
PY

ws4 dhi ingest \
  --raster /tmp/northisland_dhi.tif \
  --blocks /tmp/northisland_blocks.geojson \
  --output /tmp/northisland_dhi_values.csv \
  --metadata /tmp/northisland_dhi_metadata.json \
  --source-version "MODIS 6.1 Terra NDVI Composite RGB (2003-2022)" \
  --retrieved-utc "2026-10-26T00:00:00+00:00"

ws4 simulate --dataset femic/external/femic-northisland-instance/runtime/matrix \
  --schedule femic/external/femic-northisland-instance/runtime/baseline/schedule.csv \
  --years 31 --topology /tmp/northisland_topology.csv --resilience \
  --dhi-values /tmp/northisland_dhi_values.csv \
  --dhi-metadata /tmp/northisland_dhi_metadata.json \
  --out /tmp/ni-baseline

ws4 simulate --dataset femic/external/femic-northisland-instance/runtime/matrix \
  --schedule femic/external/femic-northisland-instance/runtime/scenario_retain_low/schedule.csv \
  --years 31 --topology /tmp/northisland_topology.csv --resilience \
  --dhi-values /tmp/northisland_dhi_values.csv \
  --dhi-metadata /tmp/northisland_dhi_metadata.json \
  --out /tmp/ni-retain-low

ws4 resilience compare --run-a /tmp/ni-baseline --run-b /tmp/ni-retain-low \
  --output /tmp/ni-resilience-comparison.csv
ws4 report --run /tmp/ni-baseline --targets examples/resilience_pilot/targets.yaml
```

Topology derivation used polygon `touches` over the corrected 3005 geometry. The
block graph is scale-dependent; it does not see within-block structure.

## Verification

Documentation-only change; `python scripts/dashboard.py` -> **GREEN** (tests
153.86 s).

## Recommendation

Adopt the DHI and resilience accounts for reporting on the North Island pilot;
do not put them in the objective yet. Before claiming the structure habitat
account, resolve the metric gap above. The next model-integration candidate
should be chosen after that decision; DIS-04 (post-fire recovery/regeneration
failure) remains the strongest next data-contract candidate.
