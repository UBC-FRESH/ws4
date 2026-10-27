# TFL 6 species composition pilot

First INV-05 slice: ingest the public **NTEMS Annual Tree Species 2022**
dominant-species layer and compare it with VRI leading species on the seven TFL 6
VRI blocks.

## Source

- Product: Annual Tree Species (1984-2022), Natural Resources Canada / NTEMS.
- Layer: `CA_Forest_Tree_Species_2022` (dominant/leading species).
- Native grid: 30 m, NAD83 Lambert Conformal Conic.
- Licence: Open Government Licence - Canada.
- Citation: Hermosilla et al. 2024, *Characterizing long-term tree species
  dynamics in Canada's forested ecosystems using annual time series remote
  sensing data*, Forest Ecology and Management 122313.

The layer carries **one dominant class per 30 m cell**, not species fractions.
This pilot therefore reports class fractions and leading species. It does not
invent a mixedwood fraction from a dominant-species product.

## Files

| File | Purpose |
| --- | --- |
| `class_map.csv` | Raster code to common/NFI/scientific name. |
| `tfl6_species_2022.tif` | 2022 species subset over the TFL 6 AOI. |
| `vri_reference.csv` | VRI leading species and species percentages. |
| `species_composition.csv` | Long block/class fractions and leading flags. |
| `species_metadata.json` | Source, year, resolution, CRS, licence, classes. |
| `vri_species_input.csv` | VRI species code/percentage columns for the pilot. |
| `vri_code_map.csv` | VRI species code to NFI class. |
| `species_fractions.csv` | Long VRI species fractions and leading flags. |
| `species_fractions_summary.csv` | Leading fraction, non-leading fraction, species count. |
| `species_fractions_metadata.json` | Fraction source, columns, code map, missing blocks. |
| `species_comparison.csv` | NTEMS leading species vs VRI, with VRI fraction summary. |
| `species_comparison_summary.json` | Compared blocks, matches, agreement, gaps. |

## Commands

```bash
ws4 species ingest \
  --raster examples/species_tfl6/tfl6_species_2022.tif \
  --blocks .../runtime/dem/p79_7_canopy_pilot/vri_aoi.geojson \
  --class-map examples/species_tfl6/class_map.csv \
  --output examples/species_tfl6/species_composition.csv \
  --metadata examples/species_tfl6/species_metadata.json \
  --source-version "CA_Tree_Species_Classification_2022" \
  --year 2022 \
  --block-id-field feature_id

ws4 species fractions \
  --table examples/species_tfl6/vri_species_input.csv \
  --class-map examples/species_tfl6/class_map.csv \
  --code-map examples/species_tfl6/vri_code_map.csv \
  --output examples/species_tfl6/species_fractions.csv \
  --metadata examples/species_tfl6/species_fractions_metadata.json \
  --summary examples/species_tfl6/species_fractions_summary.csv \
  --source-version "TFL6 VRI 2025 species percentages" \
  --source-id bc-vri-tfl6 --allow-missing

ws4 species compare \
  --composition examples/species_tfl6/species_composition.csv \
  --metadata examples/species_tfl6/species_metadata.json \
  --reference examples/species_tfl6/vri_reference.csv \
  --output examples/species_tfl6/species_comparison.csv \
  --summary examples/species_tfl6/species_comparison_summary.json
```

## Results

- Public layer classes in the AOI: 0 (non treed), 33 (western redcedar), and 35
  (western hemlock). No yellow-cedar (11) cells were present.
- Seven blocks: 15 block/class rows. Public leading species was western redcedar
  for all seven.
- Comparison against VRI leading species: **4 matches / 6 comparable blocks
  (66.7%)**. Mismatches: 16624698 (public 33 / VRI HW) and 16625195 (public 33 /
  VRI YC). Block 23339462 has no VRI species label and is reported as missing
  reference.
- Block 23339462 is 83.1% class 33 and 14.5% non-treed in the public layer.

## Interpretation

- The public layer is the 2022 leading species; VRI is a different inventory
  vintage and uses polygon labels. Agreement is a data-quality check, not a
  validation of either product.
- The public layer is dominant-only. It cannot provide a mixedwood fraction. All
  six VRI blocks with species data have multiple species; any mixedwood fraction
  must come from VRI, ALS, or another composition source.
- The 66.7% local agreement is lower than the national 86.1% accuracy; this tiny
  seven-block sample is not an accuracy estimate.
- Block 23339462 has no VRI species label; the comparison reports it as missing
  reference rather than assigning one.
