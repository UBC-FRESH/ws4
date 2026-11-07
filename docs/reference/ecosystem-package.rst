Ecosystem package and cohort state
==================================

Purpose
-------

The ecosystem package is an optional sidecar that declares the ecological state of a
compiled dataset. It does not change the management dataset. A dataset with no package
behaves exactly as before; the simulator, the optimizer, and every existing account keep
working. When a package is present, the engine can read cohorts, aggregate them to
fragments, and apply a declared bridge back to the management state.

The package starts with the state schema, the cohort table, and the null bridge. Process
definitions and scenarios are recorded as optional files for later tasks; this page does
not execute them.

Backward compatibility
----------------------

The package lives at:

.. code-block:: text

   dataset/
     manifest.json          # the compiled management dataset
     fragments.parquet
     ...
     ecosystem/
       manifest.json        # the optional ecosystem package
       state_variables.csv
       cohorts.csv
       bridges.csv

``find_ecosystem_package(dataset_dir)`` returns the sidecar directory or ``None``.
``load_dataset_ecosystem(dataset_dir)`` returns the loaded package or ``None``. A caller that
does not ask for the package never pays for it.

Manifest
--------

The manifest is a closed schema. Unknown fields are rejected. Required fields:

``schema_version``
   ``ws4.ecosystem.v1``.
``package_id``
   Producer-assigned identifier.
``created_utc``
   ISO-8601 creation timestamp.
``producer``
   ``name`` and ``version``.
``sources``
   A list of ``path`` and ``sha256`` records.
``table_files``
   Optional table name to file name. The defaults are ``state_variables.csv``,
   ``cohorts.csv``, and ``bridges.csv``.
``table_hashes``
   Optional table name to SHA-256 digest. When present, every digest is verified.

Optional fields:

``processes``
   A process-definition file. It is recorded and hashed, but not loaded yet.
``scenarios``
   A scenario-definition file. It is recorded and hashed, but not loaded yet.
``calibration``
   A calibration file. It is recorded and hashed, but not loaded yet.
``metadata``
   Free-form, public-safe metadata.

Package tables are CSV. A non-CSV table is rejected rather than guessed at. The package
fingerprint is a stable SHA-256 over the manifest and every loaded file.

State variables
---------------

``state_variables.csv`` declares the typed state:

.. list-table::
   :header-rows: 1
   :widths: 18 14 14 54

   * - Column
     - Type
     - Scope
     - Meaning
   * - ``name``
     - string
     - —
     - Unique variable name.
   * - ``dtype``
     - string
     - —
     - ``float``, ``int``, ``bool``, or ``string``.
   * - ``scope``
     - string
     - —
     - ``cohort``, ``fragment``, ``site``, or ``landscape``.
   * - ``unit``
     - string
     - —
     - Unit label, or empty for dimensionless.
   * - ``default``
     - string
     - —
     - Typed default, or empty when the variable has no default.
   * - ``description``
     - string
     - —
     - Human-readable description.

The cohort table requires six declared variables with scope ``cohort``:
``species`` (string), ``age`` (int), ``area_fraction`` (float), ``biomass_t_ha`` (float),
``fuel_t_ha`` (float), and ``snag_t_ha`` (float). Additional cohort-scope variables may be
carried in ``attributes_json``. The loader rejects an attribute that is not declared, and a
fixed column cannot be repeated as an attribute.

Cohorts
-------

``cohorts.csv`` stores the ecological state as area fractions of a fragment:

.. list-table::
   :header-rows: 1
   :widths: 24 16 60

   * - Column
     - Type
     - Meaning
   * - ``fragment_id``
     - integer
     - The dataset fragment. It must exist when the state is joined to a dataset.
   * - ``cohort_id``
     - integer
     - Unique within the fragment.
   * - ``species``
     - string
     - Species or species mixture label.
   * - ``age``
     - integer
     - Cohort age in years, non-negative.
   * - ``area_fraction``
     - number
     - Share of the fragment in (0, 1]. Fractions must sum to 1 per fragment.
   * - ``biomass_t_ha``
     - number
     - Live biomass, non-negative.
   * - ``fuel_t_ha``
     - number
     - Surface fuel, non-negative.
   * - ``snag_t_ha``
     - number
     - Standing dead, non-negative.
   * - ``attributes_json``
     - string
     - A JSON object of declared cohort-scope scalar attributes.

A blank numeric cell uses the declared default. A blank cell with no default is an error.
The cohort table may be empty; the package then declares a schema but no ecological state.

Aggregation
-----------

``CohortState`` joins the cohorts to a dataset's fragment areas and provides:

- ``aggregate_to_fragments()`` — one row per covered fragment with area, cohort count, and
  area-weighted age, biomass, fuel, and snags.
- ``species_fractions()`` — one row per fragment and species with area fraction and area.
- ``cohort_areas()`` — the cohort rows plus fragment area and absolute cohort area.
- ``missing_fragments()`` — dataset fragments the package does not cover.
- ``check_area_conservation()`` — every covered fragment's fractions sum to one and its
  cohort areas sum to the fragment area.

The area of a cohort is ``area_fraction × fragment area``. The aggregation is exact by
construction; the conservation check makes the invariant explicit.

The null bridge
---------------

``bridges.csv`` declares the bridge from ecological state to management state:

.. list-table::
   :header-rows: 1
   :widths: 24 20 56

   * - Column
     - Type
     - Meaning
   * - ``bridge_id``
     - string
     - Unique bridge identifier.
   * - ``type``
     - string
     - Only ``null`` is implemented.
   * - ``params_json``
     - string
     - A JSON object of bridge parameters.
   * - ``state_reads``
     - string
     - Semicolon-separated declared state variables the bridge reads.
   * - ``state_writes``
     - string
     - Semicolon-separated declared state variables the bridge writes.

The null bridge is the explicit no-op. It returns the management frame unchanged and must
not declare ``state_writes``. It is the contract the calibrated yield bridge will replace,
not a hidden default. A package must declare at least one bridge.

Command
-------

.. code-block:: bash

   ws4 ecosystem validate-package --package dataset/ecosystem
   ws4 ecosystem validate-package --package dataset/ecosystem --json

The text report shows the package id, schema version, state-variable count, cohort count,
bridge ids, and fingerprint. ``--json`` emits a stable report with a ``valid`` flag and every
finding as ``code``, ``where``, and ``message``.

Validation codes
----------------

``ECOSYSTEM-MISSING-DIR``
   The package directory does not exist.
``ECOSYSTEM-MISSING-MANIFEST``
   ``manifest.json`` is missing.
``ECOSYSTEM-BAD-MANIFEST``
   The manifest does not parse or has an unknown field.
``ECOSYSTEM-SCHEMA-VERSION``
   The schema version is not ``ws4.ecosystem.v1``.
``ECOSYSTEM-MISSING-TABLE``
   A required table or optional file is missing.
``ECOSYSTEM-MISSING-COLUMN``
   A required column is missing.
``ECOSYSTEM-EXTRA-COLUMN``
   A table has an unexpected column.
``ECOSYSTEM-DUPLICATE``
   A declared key is not unique.
``ECOSYSTEM-TABLE-FORMAT``
   A table is not CSV.
``ECOSYSTEM-HASH``
   A table digest does not match the manifest.
``ECOSYSTEM-STATE``
   A state-variable declaration is invalid.
``ECOSYSTEM-STATE-MISSING``
   A required cohort variable is not declared.
``ECOSYSTEM-STATE-TYPE``
   A required cohort variable has the wrong dtype or scope.
``ECOSYSTEM-COHORT``
   A cohort row is invalid.
``ECOSYSTEM-COHORT-FRACTION``
   A fragment's area fractions do not sum to one.
``ECOSYSTEM-BRIDGE``
   A bridge declaration is invalid.
``ECOSYSTEM-BRIDGE-MISSING``
   The package declares no bridge.
``ECOSYSTEM-UNKNOWN-FRAGMENT``
   A cohort names a fragment outside the dataset.
``ECOSYSTEM-DATASET-MISSING``
   The dataset has no ``fragments.parquet``.
``ECOSYSTEM-DATASET-COLUMNS``
   The dataset fragment table lacks ``fragment_id`` or ``area_ha``.

Limits
------

- The package is dataset-independent until ``cohort_state()`` joins it. The package
  validator does not know the dataset's fragment ids.
- A fragment with no cohorts is allowed and reported by ``missing_fragments()``.
- Only the null bridge is implemented. A calibrated yield bridge is a later task.
- Process definitions and scenarios are recorded but not executed. The fire process and the
  scenario ensemble are later P144 tasks.
- Tables are CSV. A columnar cohort table is a later performance decision.

Cross-references
----------------

- :doc:`compiled-dataset`
- :doc:`event-log`
- :doc:`simulator`
- :doc:`carbon`
