# DHI biodiversity-account pilot

This is a small, reproducible **software** pilot for the Dynamic Habitat Index (DHI)
biodiversity account. It uses a real DHI raster subset over a real British Columbia
AOI, but the four blocks are synthetic 10 ha squares placed inside that AOI. The
point is to exercise the ingest, provenance, account, report, and web-layer paths, not
to make a statement about habitat at this location.

## Source

- Product: SILVIS Lab **MODIS 6.1 Terra NDVI Composite RGB**, 2003-2022.
- Coverage: global composite; this directory stores a 500 m subset around
  49.35° N, 122.80° W (EPSG:4326).
- Bands: red = cumulative DHI (`cum`), green = minimum DHI (`min`), blue =
  variation DHI (`var`); values are 8-bit scaled and divided by 255.
- Licence: public, no restrictions (SILVIS Lab).
- Download service: <https://silvis.forest.wisc.edu/data/dhis/> (WCS subset).

The subset is stored as `dhi_ndvi_terra_500m_subset.tif`; `dhi_metadata.json`
records the source version, bounding box, CRS, scale, SHA-256, and retrieval time.

## Files

| File | Purpose |
| --- | --- |
| `dhi_ndvi_terra_500m_subset.tif` | Real DHI WCS subset used by the pilot. |
| `blocks.geojson` | Four synthetic 10 ha blocks in EPSG:3005. |
| `recipe.xml` | The WS4 sample recipe; growth is unchanged by DHI. |
| `fragments.csv` | The four blocks, ages 40-100, unmanaged. |
| `schedule_baseline.csv` | No treatments. |
| `schedule_harvest.csv` | Harvest block 1 at offset 0 and block 3 at offset 5. |
| `dhi_values.csv` | Block DHI values produced by the ingest. |
| `dhi_metadata.json` | Provenance for those values. |

## Run it

```bash
ws4 dhi ingest \
  --raster examples/dhi_pilot/dhi_ndvi_terra_500m_subset.tif \
  --blocks examples/dhi_pilot/blocks.geojson \
  --output examples/dhi_pilot/dhi_values.csv \
  --metadata examples/dhi_pilot/dhi_metadata.json \
  --source-version "MODIS 6.1 Terra NDVI Composite RGB (2003-2022)"

ws4 build --xml examples/dhi_pilot/recipe.xml \
  --fragments examples/dhi_pilot/fragments.csv --out build/dhi_pilot

ws4 simulate --dataset build/dhi_pilot \
  --schedule examples/dhi_pilot/schedule_harvest.csv --years 10 \
  --dhi-values examples/dhi_pilot/dhi_values.csv \
  --dhi-metadata examples/dhi_pilot/dhi_metadata.json \
  --out runs/dhi_harvest

ws4 report --run runs/dhi_harvest \
  --targets examples/dhi_pilot/targets.yaml
```

The baseline run keeps `feature.DHI.area` at 40 ha. The harvest run drops it to
20 ha after the two scheduled blocks are treated. The DHI totals fall with the
removed block area; the area-weighted means fall only when the remaining blocks
differ from the removed ones.

## What the account means

`feature.DHI.<band>` is a **level** in index-hectares: the sum of block DHI
× block area for blocks not yet treated. `feature.DHI.<band>.mean` is the
area-weighted mean index over those blocks. `feature.DHI.area` is the surviving
area in hectares.

A block leaves the account when any scheduled treatment is applied. The pilot does
not model regrowth, recovery, species response, or a habitat-suitability model.
This is a schedule-dependent biodiversity **surrogate**, not a species observation.

## Caveats

- 500 m pixels are much coarser than the 10 ha blocks. Sampling uses all touched
  pixels, so a block can inherit a neighbouring pixel's value. Do not read the
  block values as field measurements.
- The source is a 2003-2022 composite, not an annual time series. The account's
  change over time comes from the schedule, not from interannual DHI change.
- The synthetic block layout is for software tests. Use real block polygons and a
  real inventory before making management claims.
- DHI is a productivity/seasonality surrogate. It does not establish species
  presence, habitat quality, or a causal management effect.
