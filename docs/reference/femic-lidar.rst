FEMIC LidarBC Products
======================

WS4 consumes versioned FEMIC LidarBC product bundles. It does not run LiDAR
discovery, materialization, terrain compilation, or canopy processing.

Bundle Contract
---------------

A FEMIC bundle contains ``manifest.json``, ``provenance/selection.json``, and
``products/``. WS4 pins:

- ``bundle_id`` and ``bundle_version``;
- ``manifest_sha256``;
- each product ``sha256`` and ``relative_path``.

``ws4.io.lidar.load_femic_lidar_bundle`` validates the manifest, checksums,
OGL-BC licence, native CRS, per-product resolution and vertical datum, and
source-tile membership.

Python Usage
------------

.. code-block:: python

   from pathlib import Path
   from ws4.io.lidar import (
       bundle_pin,
       load_femic_lidar_bundle,
       summarize_femic_lidar_for_polygons,
   )

   bundle = load_femic_lidar_bundle(
       Path("data/femic/lidarbc-2026.10.0"),
       expected_bundle_id="lidarbc-995fb1f771f4d7fe",
   )
   pin = bundle_pin(bundle)
   rows = summarize_femic_lidar_for_polygons(
       bundle,
       Path("data/blocks.gpkg"),
       product="slope",
       id_field="block_id",
   )

Polygon summaries require ``ws4[lidar]``. Polygon and product CRS must match;
there is no silent reprojection or resampling.

Registration
------------

Register a validated bundle in a compiled dataset:

.. code-block:: bash

   ws4 lidar register \
     --dataset build/compiled \
     --bundle data/femic/lidarbc-2026.10.0 \
     --bundle-id lidarbc-995fb1f771f4d7fe \
     --bundle-version 2026.10.0-tfl6-pilot

   ws4 lidar inspect --dataset build/compiled
   ws4 lidar validate --dataset build/compiled

Registration writes the pin to ``manifest.json`` under
``metadata.lidar_products`` and to a ``lidar_products.json`` sidecar. The bundle
is referenced, not copied.

The same registration is available during a build:

.. code-block:: bash

   ws4 build --xml recipe.xml --fragments fragments.parquet --out build/compiled \
     --lidar-bundle data/femic/lidarbc-2026.10.0 \
     --lidar-bundle-id lidarbc-995fb1f771f4d7fe \
     --lidar-bundle-version 2026.10.0-tfl6-pilot

Fragment And Block Mapping
--------------------------

Map registered products to fragment and block support:

.. code-block:: bash

   ws4 lidar map \
     --dataset build/compiled \
     --fragments data/fragments.gpkg \
     --out build/lidar_mapping \
     --product slope \
     --product chm \
     --statistic mean \
     --statistic p95

Fragment rows are zonal statistics over each fragment polygon. Block rows are
zonal statistics over the dissolved block geometry. The default fields are
``fragment_id``, ``block_id``, and ``area_ha``; override them with
``--fragment-id-field``, ``--block-id-field``, and ``--area-field``.

The output includes ``lidar_fragments.csv``, ``lidar_blocks.csv``, and
``lidar_mapping_manifest.json``. The manifest records the bundle pin, product
checksums, CRS, native resolution, statistics, and explicit aggregation rules.
No resampling or reprojection is performed.

Canopy And Precision Forestry
-----------------------------

Map CHM height/cover and optional tree/VRI evidence:

.. code-block:: bash

   ws4 lidar canopy \
     --dataset build/compiled \
     --fragments data/fragments.gpkg \
     --out build/canopy_mapping \
     --vri data/vri.gpkg \
     --tree-product individual_tree

The mapping records CHM mean/p90/p95/max and cover at 2/5/10 m for fragments and
dissolved blocks. With ``--vri`` it adds area-weighted VRI height/closure and
CHM-minus-VRI deltas plus uncertainty summaries. With ``--tree-product`` it adds
tree counts, height mean/p95, and species counts per support.

The manifest records bundle provenance, checksums, CRS, native resolution,
aggregation rules, VRI uncertainty, tree summary, and explicit caveats. CHM
cover at >=2 m is not VRI crown-closure equivalence. No segmentation or raw
point-cloud processing is implemented.

Shared Parity
-------------

The WS4 and FHOPS consumer contracts were validated against FEMIC bundle
``lidarbc-995fb1f771f4d7fe`` over seven shared TFL 6 polygons. Slope and CHM
mean/p95 values matched exactly (maximum absolute difference ``0.0``).
