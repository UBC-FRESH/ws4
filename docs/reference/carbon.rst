.. _carbon:

Carbon accounting and planning
==============================

WS4 does not derive the CBM science crosswalks itself. It reads a **carbon package**
produced by FEMIC, validates it, joins it to the compiled dataset by track name, and then
compiles the schedule-dependent SIT tables. The package is the cross-repo contract; the
carbon engine is replaceable behind it.

The page has three jobs: it is the consumer-side package contract, the runtime reference
for the libcbm path and the optimizer ledger, and the map to the public evidence and the
producer-side pages. The task walkthrough is :doc:`../howto/run-carbon`.

.. contents:: On this page
   :local:
   :depth: 2

Start here
----------

.. list-table::
   :header-rows: 1
   :widths: 24 42 34

   * - If you are
     - Read
     - Why
   * - A planner or analyst
     - :doc:`../howto/run-carbon`, then :ref:`carbon-running`, :ref:`carbon-targets`,
       and :ref:`carbon-hwp`
     - The shortest path from a compiled dataset and a FEMIC package to a carbon-aware
       schedule.
   * - A developer
     - :ref:`carbon-package-layout`, :ref:`carbon-sit`, :ref:`carbon-api`, and
       ``notes/design/ws4-carbon.md``
     - The tables, the join key, the SIT boundary, and the historical design note.
   * - A researcher or policy analyst
     - :ref:`carbon-hwp`, :ref:`carbon-gcbm`, and :ref:`carbon-evidence`
     - What is counted, what is assumed, and what the model does not claim.
   * - An LLM agent
     - This page, ``docs/llms.txt``, and ``AGENTS.md``
     - The stable source-of-truth map before changing the carbon lane.

At a glance
-----------

.. mermaid::

   flowchart LR
     F[FEMIC carbon package] --> P[WS4 package loader]
     D[WS4 compiled dataset] --> S[SIT compiler]
     C[Schedule] --> S
     P --> S
     S --> E[libcbm driver]
     E --> A[carbon.* ecosystem accounts]
     A --> L[stand-state optimizer ledger]
     A --> R[run report and web Carbon tab]
     A --> H[HWP lifecycle]
     H --> Y[system carbon and emissions]
     G[GCBM results database] -. bridge only .-> W[GCBM reader]

The package is static inventory and crosswalks. WS4 adds the schedule, the treatment
transitions, and the product lifecycle. The block ledger can price a carbon target
without rerunning a whole landscape; the exact ``ws4 carbon`` run remains the reported
authority.

Source-of-truth map
-------------------

.. list-table::
   :header-rows: 1
   :widths: 30 44 26

   * - Question
     - Read
     - Stable location
   * - What must a producer package contain?
     - FEMIC forest carbon domain contract
     - `FEMIC contract <https://ubc-fresh.github.io/femic/reference/contracts/carbon-domain.html>`_
   * - How do I export and validate a package?
     - FEMIC carbon package export guide
     - `FEMIC export guide <https://ubc-fresh.github.io/femic/guides/carbon-export.html>`_
   * - What are the HWP and displacement assumptions?
     - FEMIC HWP lifecycle guide and public config
     - `FEMIC HWP guide <https://ubc-fresh.github.io/femic/guides/hwp-lifecycle.html>`_
   * - What is the public curve and HWP method?
     - The thesis and ``fresh-yan`` records
     - `Thesis <https://github.com/UBC-FRESH/yan-yancun-masc-thesis-paper>`_,
       `fresh-yan <https://github.com/UBC-FRESH/fresh-yan>`_
   * - How is WS4 wired?
     - ``ws4/carbon/package.py``, ``sit.py``, ``libcbm.py``, ``hwp.py``,
       ``curves.py``, ``ledger.py``
     - This page and the package docstrings
   * - What did the production runs show?
     - ``notes/reports/p120-multi-boundary.md`` and the P58 reports
     - ``notes/reports/``

Producer contract and package boundary
--------------------------------------

The producer side is specified in FEMIC's ``docs/reference/contracts/carbon-domain.rst``.
This page specifies what WS4 accepts and how it fails.

.. _carbon-package-layout:

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
   ``historic_disturbance``, ``last_pass_disturbance``, and optional
   ``eco_boundary``. Area is positive; age and delay are non-negative; land class is
   0-22. A disturbance must appear as a user type or a default type in
   ``disturbance_types.csv``. When ``eco_boundary`` is present, WS4 splits a track's
   dataset area across its inventory boundary shares. WS4 sums identical
   classifier/age rows before handing the SIT inventory to libcbm.

``yield.csv``
   ``track_name``, ``species``, ``leading_species``, ``age``, ``volume_m3_ha``. The
   ``track_name``/``species``/``age`` key is unique; age and volume are non-negative.
   Every track in the track map has at least one yield row.

``track_carbon_map.csv``
   ``track_name``, ``classifier_set``, ``leading_species``, ``softwood_share``,
   ``hardwood_share``, ``landclass``, ``last_disturbance``, ``eco_boundary``,
   ``volume_feature_label``. ``classifier_set`` is a semicolon-separated list in
   ascending ``classifier_id`` order. Shares are in 0-1 and sum to at most one. Every
   leading species is in ``species_map.csv``. Every track's eco boundary must appear in
   ``boundaries.csv`` for the manifest administrative boundary.

``curve_carbon_map.csv``
   ``track_name``, ``feature_label``, ``species``, ``share``. It maps a WS4 feature
   label to a species component. The key is unique; share is in 0-1.

``species_map.csv``
   ``bc_species``, ``cbm_species``, ``wood_type``, ``confidence``, and optional
   ``notes``. ``wood_type`` is ``softwood`` or ``hardwood``. The table is unique by
   ``bc_species``.

``boundaries.csv``
   ``admin_boundary`` and ``eco_boundary``, with optional ``spatial_unit_id``,
   ``source``, and ``notes``. At least one row must match the manifest primary
   boundary. A package may declare more than one eco boundary; WS4 then compiles the
   SIT ``admin_boundary`` and ``eco_boundary`` classifiers and uses
   ``SeparateAdminEcoClassifiers`` so each track gets its own CBM spatial unit. If
   the inventory carries per-row ``eco_boundary``, a track's dataset area is split by
   the package inventory shares rather than assigned wholly to its dominant boundary.

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

.. _carbon-sit:

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
- sums identical inventory rows and identical events before libcbm, because CBM is
  area-additive;
- maps each WS4 treatment to its package disturbance type;
- rejects a retention split with ``CARBON-RETENTION-UNSUPPORTED`` rather than
  approximating it;
- rejects an unknown treatment, block, track, or missing dataset table with a stable
  finding code.

The generated tables can be parsed by libcbm directly. The ``test_optional_libcbm_parse``
test does so when libcbm is installed; otherwise it skips.

.. _carbon-running:

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
     --hwp-config config/carbon/hwp.bc.yaml \
     --audit-sit

``--years`` defaults to the latest schedule offset plus one. ``--audit-sit`` writes the
generated tables under ``carbon_sit/``. ``--density`` writes tC/ha instead of tC.
``--allow-defaults-mismatch`` is only for an explicit comparison; the default is a hard
failure when the package's ``cbm_defaults`` hash differs from the installed database.
``--hwp-config`` adds the harvested-wood-product lifecycle and whole-system accounts.
``--merge-into <run-dir>`` merges the ``carbon.*`` and ``fertilization.*`` accounts into
an existing simulation run's ``account_values.csv`` and copies ``carbon_manifest.json``
beside it. Existing carbon/fertilization rows are replaced, so a rerun is idempotent;
other accounts are preserved.

The run writes:

- ``carbon_pools.csv`` and ``carbon_pools_long.csv``
- ``carbon_flux.csv`` and ``carbon_flux_long.csv``
- ``carbon_accounts.csv`` with the ``carbon.*`` accounts and, when configured,
  ``fertilization.*`` and HWP/system accounts
- ``carbon_manifest.json`` with the package, dataset, schedule, engine, defaults, HWP,
  and fertilization provenance

The driver is optional: install ``ws4[carbon]`` (``libcbm==2.10.2``). A core WS4 install
does not import libcbm.

.. _carbon-targets:

Carbon targets in the optimizer
-------------------------------

`ws4 optimize --carbon-package <package>` enables carbon accounts and `carbon.*` targets.
The :class:`ws4.carbon.ledger.CarbonLedger` prices a **stand state** once, keyed by
``(track, age, treatment chain)``, and makes a block the area-weighted sum of its
fragments. Because CBM is aspatial and linear in area, the block sum is exact; the ledger
is not a surrogate. A seed can pre-price every reachable state through
``CarbonLedger.prepare`` so fork workers share the cache instead of rerunning identical
stands.

The initial schedule and the reported target values use a **whole-schedule batch**:
one libcbm model holds every fragment, only scheduled blocks carry events, and the fixed
model cost is paid once. Search moves still use the stand-state cache, so a move prices
only the blocks it touches. The batch total and the stand-state sum are the same
area-weighted accounts; the batch path is much faster for large initial schedules.

A carbon target uses the same weighted-goal objective, period semantics, normalization,
and priority tiers as any other account. A `carbon.*` target without a package is rejected
before the search. Add `--carbon-hwp <yaml>` when the target is a system account such as
``carbon.co2e.system.emissions``; the shell is the same as the ecosystem path. The run
writes carbon accounts into `account_values.csv` and the standard report, and records
`carbon_ledger.json` beside the run.

Examples of directly targetable system objectives (all need both ``--carbon-package``
and ``--carbon-hwp``):

.. code-block:: yaml

   targets:
     # Maximize end-of-horizon whole-system carbon stock.
     - account: carbon.system.total
       period: 200
       minimum: 900000000
       period_width: 1
     # Minimize cumulative net system emissions.
     - account: carbon.co2e.system.emissions.cumulative
       period: 200
       maximum: 0
       period_width: 1
     # Favor long-lived solid-wood products over paper.
     - account: carbon.hwp.solid_wood.total
       period: 200
       minimum: 1000000
       period_width: 1

The exact full-schedule run can differ slightly from the incremental stand-state sum after
a disturbance when several stands share a source track: the batched SIT run aggregates
events by classifier set and area, while the incremental move path prices stand states
and sums their area-weighted accounts. The target report uses the batch total, but the
search objective can lag it. Re-run the winning schedule with ``ws4 carbon`` and report
that result. See :doc:`../guides/limitations-and-boundaries`.

For a global keep/remove decision, ``ws4 carbon-removal`` builds an exact per-block
effect table and searches the bits on the GPU. This is useful when the constraint is a
yield floor and the carbon objective is driven by which blocks are harvested, not by
small treatment-year shifts. See :doc:`../howto/run-carbon-removal`.

Fertilization
-------------

``ws4 carbon --fertilization-config <yaml>`` enables the ``f1``, ``f2``, and ``f3``
fertilization treatments for a carbon run. The YAML can be the FEMIC public-assumption
file; the loader accepts its ``dose_kg_n_ha``, ``factors_kg_ha``, ``gwp100``, and
``growth_response`` sections. The three treatments are added to the in-memory disturbance
table as no-op CBM disturbances.

There are two growth modes. The **curve mode** is the full materialized path. Add an
``applications`` list to the YAML, one entry per source track and treatment:

.. code-block:: yaml

   applications:
     - treatment: f1
       source_track: "AU(2401005)+IFM(managed)+ORIGIN(natural)+SILV_STATE(baseline)+RETENTION(0)+treatment()"
       target_track: "AU(2401005)+IFM(managed)+ORIGIN(natural)+SILV_STATE(baseline)+RETENTION(0)+treatment()+F1"
       curve: curves/f1-2401005-natural.csv

The curve is the CSV written by ``femic carbon fertilization-curve``. WS4 copies the
source track's classifier, map, yield, and curve rows to the target track, replaces the
leading-species yield with the materialized curve, and adds a transition from the source
track. The transition uses ``reset_age: -1`` so the stand keeps its age; CBM then grows
the same stand on the fertilized curve. WS4 also adds a recovery event at
``offset + response_years`` that transitions the target track back to the source track,
again without resetting the age, so the growth uplift is temporary. The recovery event is
visible in the ``--audit-sit`` event and transition tables.
``target_track`` is optional and defaults to
``<source_track>+<TREATMENT>``. A curve applies to every block on that source track that
receives the treatment. The treatment event still updates CBM's disturbance clock, so an
eligibility rule based on years since disturbance sees fertilization as an event; the
stand age is preserved.

If no ``applications`` are declared, WS4 falls back to the **multiplier mode**: after a
fertilizer event it applies the configured ``growth_multiplier`` (default ``1.10``) to
annual growth for ``response_years`` (10 by default). Use the materialized curve for
per-track responses; use the multiplier only for a scalar calibration or a quick run.

The run writes these accounts into ``carbon_accounts.csv`` in both modes:

- ``fertilization.area_ha`` and ``fertilization.dose_kg_n``
- ``fertilization.co2_t``, ``fertilization.ch4_t``, ``fertilization.n2o_t``
- ``fertilization.co2e_t``

``carbon_manifest.json`` records the mode, curve applications, growth window,
multiplier, factors, GWP values, and account totals under ``fertilization``.
``ws4 optimize --carbon-package <package> --carbon-fertilization <yaml>`` passes the same
configuration to the block ledger, so carbon targets and the run report include both the
growth delta and the emissions. A schedule with no ``f1``/``f2``/``f3`` event is
unchanged.

.. _carbon-hwp:

Harvested wood products and system carbon
-----------------------------------------

Ecosystem carbon alone is not the forest-sector balance. With
``--hwp-config <yaml>`` (or ``--carbon-hwp`` in the optimizer), WS4 turns the
merchantable carbon transferred by each disturbance into an explicit HWP ledger. The
public assumptions live in FEMIC's ``config/carbon/hwp.bc.yaml`` and are documented in the
`FEMIC HWP lifecycle guide <https://ubc-fresh.github.io/femic/guides/hwp-lifecycle.html>`_.

The method follows the corrected public accounting in ``fresh-yan``:

- utilized inflow is ``merchantable carbon transferred x utilization_rate``;
- utilized fibre is split into solid wood and paper;
- each pool survives a period with the exact factor
  ``2 ** (-period_length / half_life)``;
- the loss from a product pool is an end-of-life emission to the atmosphere; and
- displacement is a credit on product inflow, in tC avoided per tC product, converted to
  CO2e with the 44/12 factor.

The default public parameter file uses 85% utilization, a 50/50 paper/solid split, a
two-year paper half-life, and a representative solid-wood half-life and displacement
factor. Those are scenario parameters, not a calibrated estimate: run a grid over
plausible half-lives and displacement factors and report the range.

The HWP path adds these accounts to ``carbon_accounts.csv``:

``carbon.hwp.solid_wood.total``, ``carbon.hwp.paper.total``, ``carbon.hwp.total``
   Product pools in tC.
``carbon.hwp.inflow``
   Annual product inflow in tC.
``carbon.hwp.decay`` and ``carbon.co2e.hwp.eol``
   Annual product decay in tC and end-of-life emissions in tCO2e.
``carbon.displacement.total`` and ``carbon.co2e.displacement``
   Displacement credit in tC and tCO2e.
``carbon.system.total`` and ``carbon.co2e.system.total``
   Ecosystem carbon plus product pools, in tC and tCO2e.
``carbon.co2e.hwp.total`` and ``carbon.co2e.ecosystem.emissions``
   Product stock and ecosystem emissions in tCO2e.
``carbon.co2e.system.emissions`` and ``carbon.co2e.system.emissions.cumulative``
   Per-period and cumulative net system emissions, in tCO2e.

``carbon.products.total`` remains the engine's own ``Products`` pool. It is not the HWP
ledger: CBM's product pool carries CBM's decay assumptions, while ``carbon.hwp.*`` uses
the explicit public half-life and displacement parameters. Do not add the two together.

The lifecycle is a first version with a stated boundary: decay is immediate EOL emission
and there is no landfill or inert long-lived product pool. The forest-sector balance is
still complete in the sense that carbon leaving the ecosystem enters a product pool or the
atmosphere exactly once. The public thesis and ``fresh-yan`` records are the method
references; the WS4 implementation is ``ws4/carbon/hwp.py``.

.. _carbon-curves:

Carbon yield curves
-------------------

``ws4 carbon-curves`` compiles stock and emission curves per package track from
single-stand libcbm runs. It ports the public "simulated clearcut" method:

- a managed curve grows the source stand to a rotation age;
- a clearcut transfers the pools and emits the disturbance losses;
- the post-event trajectory becomes the age-0 managed curve; and
- ``--mode cycle`` repeats the clearcut and extracts the last cycle, which represents a
  regenerated stand rather than only a first rotation.

.. code-block:: bash

   ws4 carbon-curves \
     --dataset output/ws4/tsa24/compiled \
     --package output/carbon/tsa24 \
     --out out/carbon/tsa24-curves \
     --rotation-age 120 \
     --years 300 \
     --mode cycle

The run writes ``carbon_curves.csv`` and ``carbon_curves_manifest.json``. The table is
long by ``track_name`` and ``age`` and carries ecosystem, biomass, DOM, merchantable,
product, total-emission, gross-growth, and net-emission values per hectare. ``age`` is
time since the curve start: a natural curve starts from the one-year inventory convention,
while a managed curve starts at the post-clearcut age 0. ``products_tc_ha`` is the CBM
``Products`` pool, not the explicit HWP ledger; do not add it to ``carbon.hwp.*``. The
manifest records the package fingerprint, dataset reference, rotation age, mode, the
managed-source map, units, and the boundary that the curves are an audit/interchange
artifact.

The curve artifact is useful for a reduced LP or for external scenario formulation. The
optimizer's exact path remains the block ledger; a curve-based surrogate must be labelled
as a surrogate and verified with the exact engine before a result is reported. The public
method and its reset-error evidence are in the thesis and the ``fresh-yan`` repository.

.. _carbon-gcbm:

GCBM results
------------

`ws4 gcbm --results gcbm_output.db --out <dir>` reads a raw GCBM results database
without FLINT or Wine. It joins the GCBM pool and flux tables through the location and
date dimensions, writes `gcbm_pools.csv`, `gcbm_fluxes.csv`, `gcbm_accounts.csv`, and
`gcbm_manifest.json`, and exposes the same `carbon.*` account names as the WS4 path.
`--compare-carbon <run-dir>` writes `gcbm_compare.csv` against a WS4
`carbon_accounts.csv`.

The reader is tabular. The FEMIC walltowall export is the producer-side bridge; a
same-footprint 500-block coarse project has been prepared and run as a format/readiness
check. That check is not a parity result: GCBM and libcbm are separate CFS CBM
implementations, and WS4 deliberately does not target numerical equality with GCBM. See
the P120 handoff report and ``notes/reports/p589-gcbm-results.md`` for the evidence and
the remaining spatial-mapping boundary.

.. _carbon-evidence:

Validation and evidence
-----------------------

``scripts/carbon_parity.py`` compares two carbon run directories on
``(timestep, identifier)`` and exits nonzero when a pool or flux is outside the requested
tolerance. ``ws4.carbon.parity`` exposes the same comparison, a mass-balance/account
reconciliation table, and a byte-level replay check. The P58.5 report records the exact
WS3/WS4 parity on the clipped TSA24 fixture and the real TSA24 replay evidence.

The production evidence now includes:

- exact WS3/WS4 parity on the clipped TSA24 fixture (``max_abs = 0.0``);
- validated split-TSA packages and compiled-matrix runs for TSA08, TSA16, TSA40, and
  TSA41, with the real CBM defaults hash and no mismatch override;
- full-landscape 50-year all-block schedules for those four TSAs, with inventory and event
  aggregation; and
- a GCBM walltowall bridge run whose purpose is format/readiness, not numerical parity.

The consolidated numbers, package ids, and caveats are in
``notes/reports/p120-multi-boundary.md``. The TSA24 ledger/exact subset difference of
about 0.03% after disturbances remains a documented caveat; the exact run is the reported
outcome.

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
     - A track eco boundary is not declared in ``boundaries.csv``.
   * - ``CARBON-TABLE-HASH``
     - A table digest differs from the manifest.
   * - ``CARBON-UNMATCHED-TRACK``
     - The dataset has a track the package does not.
   * - ``CARBON-DUPLICATE-TRACK-NAME``
     - The dataset has duplicate track names.
   * - ``CARBON-BOUNDARY-MISMATCH``
     - The manifest primary boundary and the declared boundary table disagree.
   * - ``CARBON-MAPPING``
     - The manifest mapping contract is malformed or inconsistent.
   * - ``CARBON-MISSING-YIELD``
     - A package track has no yield row.
   * - ``CARBON-TABLE-EMPTY``
     - A required table has no rows.
   * - ``CARBON-TABLE-INVALID``
     - A table cannot be parsed or violates its row/column shape.
   * - ``CARBON-UNKNOWN-TABLE``
     - ``table_files`` names a table that is not part of the contract.
   * - ``CARBON-RETENTION-UNSUPPORTED``
     - The SIT compiler refuses a retention split rather than approximating it.
   * - ``CARBON-SCHEDULE-COLUMN`` / ``CARBON-SCHEDULE-OFFSET``
     - The schedule is missing a column or uses an invalid offset clock.
   * - ``CARBON-DATASET-TABLE``
     - A required compiled-dataset table is absent from the SIT compile.

The package loader and the SIT compiler share the ``CARBON-`` prefix but are different
surfaces: the first rejects a malformed package, the second rejects a package/schedule/
dataset combination that cannot be compiled faithfully.

.. _carbon-api:

API
---

.. code-block:: python

   from pathlib import Path

   from ws4.carbon.hwp import load_hwp_config
   from ws4.carbon.package import load_carbon_package, resolve_tracks

   package = load_carbon_package(Path("carbon_package"))
   resolution = resolve_tracks(package, tracks)
   track_id = resolution.mapping["AU(1)+IFM(managed)+treatment()"]
   hwp = load_hwp_config(Path("config/carbon/hwp.bc.yaml"))

``validate_carbon_package(path)`` returns every finding instead of raising.
``load_carbon_package(path)`` raises ``CarbonPackageError`` when the package is invalid.
``generate_carbon_curves(package, dataset_dir, out_dir, ...)`` writes the simulated-
clearcut curves. ``hwp_accounts(ecosystem, production, config)`` is the pure lifecycle
function behind the HWP accounts.

Implementation status
---------------------

P58 delivered the package loader, SIT compiler, libcbm driver, run report and
provenance, parity/replay checks, block ledger, carbon targets, and GCBM reader.
The fertilization runtime followed in WS4 #441. P120 added split-TSA packages and
compiled-matrix runs for TSA08, TSA16, TSA40, and TSA41, plus inventory/event
aggregation for full-landscape schedules. The HWP lifecycle and simulated-clearcut curve
compile are part of this same contract.

The public evidence map is:

- ``notes/reports/p58-closeout.md`` — P58 delivered work and deferred items;
- ``notes/reports/p58-fertilization-runtime.md`` — fertilization curve, recovery, and
  emissions;
- ``notes/reports/p585-parity.md``, ``p587-carbon-optimizer.md``,
  ``p588-carbon-validation.md``, ``p589-gcbm-results.md`` — validation and GCBM boundary;
- ``notes/reports/p120-multi-boundary.md`` — production package and landscape evidence.

Web UI
------

The **Carbon** tab in the optional web service reads the run's ``carbon_manifest.json``,
``carbon_accounts.csv``, ``carbon_pools.csv``, ``carbon_flux.csv``, ``carbon_ledger.json``, and
``gcbm_compare.csv``. It aggregates pools and fluxes by timestep and never reruns libcbm. See
:doc:`web` for the endpoint. Carbon-only run directories are listed as ``carbon`` runs; their
periods are read from the carbon account offsets.

Related across repositories
---------------------------

- `FEMIC carbon package export <https://ubc-fresh.github.io/femic/guides/carbon-export.html>`_
- `FEMIC forest carbon domain contract <https://ubc-fresh.github.io/femic/reference/contracts/carbon-domain.html>`_
- `FEMIC HWP lifecycle and public assumptions <https://ubc-fresh.github.io/femic/guides/hwp-lifecycle.html>`_
- `fresh-yan <https://github.com/UBC-FRESH/fresh-yan>`_ — public corrected accounting,
  carbon curve generation, HWP grid, and reproducible records.
- `yan-yancun-masc-thesis-paper <https://github.com/UBC-FRESH/yan-yancun-masc-thesis-paper>`_
  — manuscript methods and evidence.
- :doc:`../howto/run-carbon` — task walkthrough.
- :doc:`../guides/limitations-and-boundaries` — runtime and evidence caveats.
