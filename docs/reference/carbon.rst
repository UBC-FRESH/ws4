Carbon Package Contract
=======================

WS4 does not derive the CBM science crosswalks itself. It reads a **carbon package**
produced by FEMIC, validates it, joins it to the compiled dataset by track name, and then
compiles the schedule-dependent SIT tables. The package is the cross-repo contract; the
carbon engine is replaceable behind it.

The producer side is specified in FEMIC's ``docs/reference/contracts/carbon-domain.rst``.
This page specifies what WS4 accepts and how it fails.

Package layout
--------------

A package is a directory with a manifest and nine CSV tables:

.. code-block:: text

   carbon_package/
     manifest.json
     classifiers.csv
     disturbance_types.csv
     age_classes.csv
     inventory.csv
     yield.csv
     track_carbon_map.csv
     curve_carbon_map.csv
     species_map.csv
     boundaries.csv

CSV is the interchange form. Strings are read as strings so classifier codes keep their
leading characters. Extra columns are preserved; the required columns below are enforced.

Manifest
--------

``manifest.json`` is validated as a closed schema. Unknown fields are rejected so a typo
does not silently disable a check.

Required fields:

``schema_version``
   Package schema version. WS4 supports ``0.1``.

``package_id``
   Producer-assigned identifier.

``created_utc``
   ISO-8601 creation timestamp.

``producer``
   ``name`` and ``version``.

``sources``
   A list of upstream ``path`` and ``sha256`` records.

``cbm_defaults``
   ``version``, ``sha256``, and ``source`` of the CBM default parameter database.

``units``
   ``area``, ``volume``, ``carbon``, ``carbon_density``, and ``co2e``. WS4 requires
   ``ha``, ``m3/ha``, ``tC``, ``tC/ha``, and ``tCO2e``.

``boundaries``
   ``admin`` and ``eco`` CBM boundary names.

``mapping``
   ``track_key`` must be ``track_name``; ``species_classifier`` names the species
   classifier; ``disturbance_classifier`` must be ``user_dist_type``.

``event_source``
   Normally ``ws4.schedule``.

``transition_source``
   Normally ``ws4.treatments``.

``table_files``
   Optional table name to file name mapping. It defaults to the layout above.

``table_hashes``
   Optional table name to SHA-256 digest. When present, WS4 verifies every digest.

Tables
------

``classifiers.csv``
   ``classifier_id``, ``classifier``, ``value``. A classifier id has one name; a
   ``classifier_id``/``value`` pair is unique. ``description`` is optional.

``disturbance_types.csv``
   ``user_dist_type``, ``default_dist_type``, ``removes_biomass``,
   ``transition_reset_age``, ``regen_delay``. ``removes_biomass`` accepts the usual
   boolean spellings; the ages are non-negative numbers.

``age_classes.csv``
   ``name`` and ``class_size``. The first row has size 0; every later row has a positive,
   constant width.

``inventory.csv``
   ``track_name``, ``age``, ``area_ha``, ``delay``, ``landclass``,
   ``historic_disturbance``, ``last_pass_disturbance``. Area is positive; age and delay
   are non-negative; land class is 0-22. A disturbance must appear as a user type or a
   default type in ``disturbance_types.csv``.

``yield.csv``
   ``track_name``, ``species``, ``leading_species``, ``age``, ``volume_m3_ha``. The
   ``track_name``/``species``/``age`` key is unique; age and volume are non-negative.
   Every track in the track map has at least one yield row.

``track_carbon_map.csv``
   ``track_name``, ``classifier_set``, ``leading_species``, ``softwood_share``,
   ``hardwood_share``, ``landclass``, ``last_disturbance``, ``eco_boundary``,
   ``volume_feature_label``. ``classifier_set`` is a semicolon-separated list in
   ascending ``classifier_id`` order. Shares are in 0-1 and sum to at most one. Every
   leading species is in ``species_map.csv``. Every track's eco boundary matches the
   manifest.

``curve_carbon_map.csv``
   ``track_name``, ``feature_label``, ``species``, ``share``. It maps a WS4 feature
   label to a species component. The key is unique; share is in 0-1.

``species_map.csv``
   ``bc_species``, ``cbm_species``, ``wood_type``, ``confidence``, and optional
   ``notes``. ``wood_type`` is ``softwood`` or ``hardwood``. The table is unique by
   ``bc_species``.

``boundaries.csv``
   ``admin_boundary`` and ``eco_boundary``, with optional ``spatial_unit_id``,
   ``source``, and ``notes``. At least one row must match the manifest boundaries.

Track join
----------

Track ids are local to a compiled dataset; track names carry the state vocabulary and are
the durable join key. ``resolve_tracks`` matches the package's ``track_name`` to the
dataset's ``tracks.name`` exactly.

An unmatched dataset track is a hard failure by default. The failure names the count and
the first ten missing names. A caller may pass ``allow_unmatched=True`` to receive the
mapping plus the unmatched/extra names, but the fallback is then explicit in the caller
and must be recorded in the run provenance.

Duplicate track names in the dataset are rejected because a join would be ambiguous.

SIT compilation
---------------

``ws4.carbon.sit.build_sit_tables`` compiles the package, the compiled dataset, and a
schedule into SIT tables. It reads ``fragments``, ``tracks``, and ``treatments`` from the
dataset; the package's ``yield`` table is authoritative, so the dataset's curves are not
resampled.

The compiler:

- resolves every dataset track by exact name;
- builds the SIT classifier, disturbance-type, age-class, inventory, yield, event, and
  transition tables;
- takes event area from the dataset fragments in the scheduled block and sets
  ``time_step = offset + 1``;
- maps each WS4 treatment to its package disturbance type;
- rejects a retention split with ``CARBON-RETENTION-UNSUPPORTED`` rather than
  approximating it;
- rejects an unknown treatment, block, track, or missing dataset table with a stable
  finding code.

The generated tables can be parsed by libcbm directly. The ``test_optional_libcbm_parse``
test does so when libcbm is installed; otherwise it skips.

Running the engine
------------------

``ws4 carbon`` loads the package, compiles the SIT tables, runs libcbm behind the driver
protocol, and writes the run outputs:

.. code-block:: bash

   ws4 carbon \
     --dataset output/ws4/tsa24/compiled \
     --package output/carbon/tsa24 \
     --schedule schedules/baseline.csv \
     --out out/carbon/tsa24-baseline \
     --years 200 \
     --audit-sit

``--years`` defaults to the latest schedule offset plus one. ``--audit-sit`` writes the
generated tables under ``carbon_sit/``. ``--density`` writes tC/ha instead of tC.
``--allow-defaults-mismatch`` is only for an explicit comparison; the default is a hard
failure when the package's ``cbm_defaults`` hash differs from the installed database.

The run writes:

- ``carbon_pools.csv`` and ``carbon_pools_long.csv``
- ``carbon_flux.csv`` and ``carbon_flux_long.csv``
- ``carbon_accounts.csv`` with the ``carbon.*`` accounts
- ``carbon_manifest.json`` with the package, dataset, schedule, engine, and defaults
  provenance

The driver is optional: install ``ws4[carbon]`` (``libcbm==2.10.2``). A core WS4 install
does not import libcbm.

Fingerprint
-----------

``package_fingerprint`` hashes the manifest and every table digest in sorted table order.
It is stable for the same files and independent of the working directory. The carbon run
manifest records it.

Failure codes
-------------

The loader returns stable codes. The most useful ones:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Code
     - Meaning
   * - ``CARBON-MISSING-DIR``
     - The package directory does not exist.
   * - ``CARBON-MISSING-MANIFEST``
     - ``manifest.json`` is absent.
   * - ``CARBON-MANIFEST-INVALID``
     - The manifest does not parse or has an unknown field.
   * - ``CARBON-SCHEMA-VERSION``
     - The schema version is not supported.
   * - ``CARBON-UNIT``
     - A declared unit is not the contract unit.
   * - ``CARBON-MISSING-TABLE``
     - A required table is absent.
   * - ``CARBON-MISSING-COLUMN``
     - A required column is absent.
   * - ``CARBON-DUPLICATE-KEY``
     - A declared table key is not unique.
   * - ``CARBON-INVALID-VALUE``
     - A value is outside its contract.
   * - ``CARBON-UNKNOWN-TRACK``
     - A table names a track absent from the track map.
   * - ``CARBON-UNKNOWN-SPECIES``
     - A table names a species absent from the species map.
   * - ``CARBON-UNKNOWN-DISTURBANCE``
     - A disturbance is not declared.
   * - ``CARBON-ECO-MISMATCH``
     - A track eco boundary differs from the manifest.
   * - ``CARBON-TABLE-HASH``
     - A table digest differs from the manifest.
   * - ``CARBON-UNMATCHED-TRACK``
     - The dataset has a track the package does not.
   * - ``CARBON-DUPLICATE-TRACK-NAME``
     - The dataset has duplicate track names.

API
---

.. code-block:: python

   from pathlib import Path
   from ws4.carbon.package import load_carbon_package, resolve_tracks

   package = load_carbon_package(Path("carbon_package"))
   resolution = resolve_tracks(package, tracks)
   track_id = resolution.mapping["AU(1)+IFM(managed)+treatment()"]

``validate_carbon_package(path)`` returns every finding instead of raising.
``load_carbon_package(path)`` raises ``CarbonPackageError`` when the package is invalid.

The next step
-------------

P51.4 merges the ``carbon.*`` accounts into the run report and the provenance surfaces.
P51.5 validates parity with WS3, mass balance, and deterministic replay on the TSA24
fixture.
