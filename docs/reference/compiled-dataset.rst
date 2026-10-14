Compiled dataset
================

The compiled matrix dataset is the runtime contract of WS4 (see ``notes/adr/0002`` and
``notes/adr/0006``). Ingestion writes it; the simulator, the optimizer, and the validator read
it. Nothing downstream reads the raw recipe or inventory.

Layout
------

A dataset is a directory with a ``manifest.json`` and one Parquet file per table.

Manifest
--------

``manifest.json`` validates against ``ws4.model.types.CanonicalDatasetManifest``:

``schema_version``
    The schema version. The current value is ``0.1``.
``tables``
    A map from logical table name to file name.
``sources``
    The source identities, each with a path and a hash.
``options``
    The compile options.
``metadata``
    Free-form metadata.

Tables
------

Every table below is required, and its listed columns are required.

.. list-table::
   :header-rows: 1
   :widths: 16 46 38

   * - Table
     - Columns
     - Meaning
   * - ``fragments``
     - ``fragment_id``, ``block_id``, ``area_ha``, ``age``, ``track_id``
     - The decision units.
   * - ``blocks``
     - ``block_id``, ``track_id``, ``offset``, ``area_ha``
     - The runtime aggregate view.
   * - ``tracks``
     - ``track_id``, ``name``
     - Succession pathways.
   * - ``strata``
     - ``track_id``, ``offset``, ``next_age``, ``cycle``
     - Development strata over offset age.
   * - ``treatments``
     - ``track_id``, ``begin``, ``end``, ``treatment``, ``new_track``, ``offset``, ``retain``
     - Available operations.
   * - ``curves``
     - ``curve_id``, ``x``, ``y``
     - Growth and yield curves.
   * - ``features``
     - ``track_id``, ``label``, ``curve_id``
     - Per-track feature curves.
   * - ``products``
     - ``track_id``, ``treatment``, ``label``, ``curve_id``
     - Product definitions.
   * - ``accounts``
     - ``group``, ``attribute``, ``account``
     - Account definitions.
   * - ``groups``
     - ``block_id``, ``group``
     - Block grouping.
   * - ``messages``
     - ``severity``, ``message``
     - Compile diagnostics.

Invariants
----------

The validator also checks:

- ``area_ha`` is non-negative in ``fragments`` and ``blocks``.
- ``age`` is non-negative in ``fragments``.
- Every ``fragments.block_id`` exists in ``blocks``.
- Every ``blocks.track_id`` exists in ``tracks``.
- Each curve's ``x`` values are strictly increasing within a ``curve_id``.

Validation
----------

Run:

.. code-block:: bash

   ws4 validate --dataset build/compiled

The command prints a table of findings and exits non-zero when the dataset is invalid. Each finding has
a stable code:

``DATASET-MISSING``
    The dataset directory does not exist.
``DATASET-MISSING-MANIFEST``
    The manifest file is missing.
``DATASET-BAD-MANIFEST``
    The manifest does not parse.
``DATASET-SCHEMA-VERSION``
    The manifest schema version differs from the supported version.
``DATASET-UNLISTED-TABLE``
    A required table is not listed in the manifest.
``DATASET-MISSING-TABLE``
    A listed table file is missing.
``DATASET-MISSING-COLUMN``
    A required column is missing.
``DATASET-COLUMN-KIND``
    A column has the wrong kind.
``DATASET-NEGATIVE-AREA``
    A negative area.
``DATASET-NEGATIVE-AGE``
    A negative age.
``DATASET-UNKNOWN-BLOCK``
    A fragment references an unknown block.
``DATASET-UNKNOWN-TRACK``
    A block references an unknown track.
``DATASET-CURVE-DOMAIN``
    A curve's domain is not strictly increasing.

API
---

.. autoclass:: ws4.model.types.CanonicalDatasetManifest
   :members:

.. autofunction:: ws4.model.schema.validate_dataset
