Species composition
===================

The first INV-05 slice ingests a public **dominant tree species** raster and
stores block-level class fractions and a leading species. It is a data-contract
layer, not a species distribution model.

Source
------

The pilot uses the Natural Resources Canada / NTEMS **Annual Tree Species
(1984-2022)** product, layer ``CA_Forest_Tree_Species_2022``:

- 30 m raster, NAD83 Lambert Conformal Conic;
- one leading species class per cell, codes 0-37;
- annual maps; the pilot uses 2022;
- Open Government Licence - Canada;
- Hermosilla et al. 2024, Forest Ecology and Management 122313.

The class map carries the raster code, common name, NFI code, and scientific name.
Class 0 is non-treed.

Contract
--------

``species_composition.csv`` is long by block and species class:

``block_id``
    Block identifier.
``species_code``, ``species_name``, ``nfi_code``
    Public class identity.
``pixel_count``, ``class_fraction``
    Valid 30 m cells in the block and their fraction.
``is_leading``
    Exactly one leading class per covered block, selected by the largest pixel
    count.

``species_metadata.json`` records the source id/version, year, native resolution,
CRS, licence, citation, full class map, and notes. A block with no valid species
pixels is an error; it is not assigned a zero or a default species.

The product is **dominant species only**. It does not contain species fractions,
so the pilot does not claim a mixedwood fraction from it. VRI species
percentages, ALS composition, or another composition source would be required for
that.

Commands
--------

.. code-block:: bash

   ws4 species ingest \
     --raster tfl6_species_2022.tif \
     --blocks vri_aoi.geojson \
     --class-map class_map.csv \
     --output species_composition.csv \
     --metadata species_metadata.json \
     --source-version "CA_Tree_Species_Classification_2022" \
     --year 2022 \
     --block-id-field feature_id

   ws4 species compare \
     --composition species_composition.csv \
     --metadata species_metadata.json \
     --reference vri_reference.csv \
     --output species_comparison.csv \
     --summary species_comparison_summary.json

The comparison selects the public leading row per block and joins the reference
leading code. It reports matches, agreement percentage, and missing public or
reference blocks. A mismatch is recorded, not smoothed away.

Pilot
-----

``examples/species_tfl6`` holds the TFL 6 VRI AOI subset, class map, VRI reference,
composition, and comparison. The public 2022 layer uses classes 0, 33, and 35 in
the AOI; it did not identify yellow-cedar (11). It gives western redcedar as the
leading species for all seven blocks. Against VRI, four of six comparable blocks
match (66.7%); block 16624698 is VRI western hemlock and block 16625195 is VRI
yellow-cedar. One block has no VRI label and is reported as missing reference.
The local agreement is not an accuracy estimate for the national product.

Caveats
-------

- A dominant-species raster is not a species-fraction layer.
- VRI and the public layer have different vintages and label semantics.
- Agreement is a data-quality check, not an accuracy validation of either
  product.
- Mixedwood fractions require a separate source; do not infer them from the
  leading class.
- The public layer has national accuracy of 86.1% +/- 0.14%, which is not a
  guarantee for this local block sample.
