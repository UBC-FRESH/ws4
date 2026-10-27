# INV-05 TFL 6 species composition pilot

Date: 2026-10-27
Candidate: INV-05
Scope: first public dominant-species ingest, not a species distribution model.

## Source

- Natural Resources Canada / NTEMS Annual Tree Species 2022, layer
  `CA_Forest_Tree_Species_2022`.
- 30 m, EPSG:3978, classes 0-37; dominant/leading species only.
- Open Government Licence - Canada.
- Hermosilla et al. 2024, Forest Ecology and Management 122313.

## Implementation

- `ws4/species.py`: class map, block raster sampling, long composition table,
  source metadata, leading-species comparison, and summary.
- `ws4 species ingest` / `ws4 species compare`.
- Schema: block/class fractions and `is_leading`; source version, year,
  resolution, CRS, licence, citation, and class map are required.
- No mixedwood fraction is inferred from a dominant-species layer.

## Pilot result

Seven TFL 6 VRI blocks. Public classes present: 0 non treed, 33 western redcedar,
35 western hemlock. Public leading species is 33 for all seven blocks.

- 4 / 6 comparable blocks agree with the VRI leading species (66.7%).
- Mismatches: block 16624698 (public 33, VRI HW) and 16625195 (public 33, VRI YC).
- Block 23339462 has no VRI species label; reported missing reference.
- Block 23339462 is 83.1% public class 33 and 14.5% non-treed.
- All six VRI blocks with species data are mixed (multiple species percentages);
  the public layer cannot represent that mixture.

The 66.7% agreement is a local data-quality check on seven blocks, not an
accuracy estimate for the national product.

## Verification

- `python -m pytest tests/test_species.py -q --no-cov` -> 5 passed.
- `python -m sphinx -b html docs ... -W` -> passed.
- Files: `examples/species_tfl6/`.
