Stand density management and the AU Explorer
============================================

WS4 is adding a **stand density management diagram (SDMD)** layer. It is a
diagnostic and constraint layer, not a growth model. It places AU yield evidence,
observed sample plots, and compiled FVS trajectories on a species/region
diagram, compares silviculture regimes as paths, and turns the reviewed result
into solver constraints. The decision is ADR 0013.

.. note::

   The layer is being built in Phase 87. This page documents the stable schema
   that ingestion, the API, the web tab, and the solver read. Ingestion,
   digitisation, the API, the web tab, and solver filtering arrive in later
   tasks.

The six tables
--------------

The contract lives in ``ws4.sdmd.schema``. A row always carries a ``source`` and
a ``review_status`` of ``unreviewed``, ``provisional``, ``reviewed``, or
``rejected``.

``plots``
    One sample plot visit: region, BEC, TSA, AU, year, stand age, site index,
    slope, aspect, elevation, plot area, sources, and review status. The primary
    key is ``(plot_id, visit_year)``.
``trees``
    One measured tree: species, DBH, height, crown ratio, expansion factor,
    live flag, damage, and source. The primary key is ``(plot_id, tree_id)``.
``stands``
    One stand summary per plot visit: age, TPH, basal area, QMD, top and mean
    height, volume, crown cover, source, and review status.
``sdmd_points``
    One AU-level point on the diagram: site index, age, top height, QMD, TPH,
    basal area, mean tree volume, relative density, SDI, maximum SDI, zone,
    source, and review status.
``regimes``
    One silviculture regime as an ordered state machine: entry age and type,
    residual basal area, removal fraction, cycle length, repeat count, post-
    treatment track, eligibility and operability expressions, and review status.
``au_constraints``
    One allowed or denied regime for one AU: entry-age window, maximum entries,
    minimum interval, maximum removal fraction, required SDMD zone, source, and
    review status. The primary key is ``(au_id, regime_id)``.

Validation
----------

``coerce_to_schema`` types a frame with nullable pandas dtypes.
``validate_frame`` checks the structure of one table: required columns, value
kinds, non-null required values, non-empty required text, and a unique primary
key. ``validate_dataset`` adds value domains and cross-table references.

Findings use stable codes:

``SDMD-MISSING-COLUMN``, ``SDMD-COLUMN-KIND``, ``SDMD-NULL-VALUE``
    Structure. A table without a required column or value cannot pass.
``SDMD-EMPTY-VALUE``
    A required text field is blank.
``SDMD-DUPLICATE-KEY``
    A primary key repeats.
``SDMD-MISSING-TABLE``, ``SDMD-UNKNOWN-TABLE``
    A required table is absent, or a name is not part of the contract.
``SDMD-RANGE``
    A numeric value is outside its domain.
``SDMD-ENTRY-WINDOW``
    A constraint's minimum entry age exceeds its maximum.
``SDMD-ENUM``
    A review status, SDMD zone, or regime entry type is unknown.
``SDMD-UNKNOWN-PLOT``, ``SDMD-UNKNOWN-REGIME``, ``SDMD-UNKNOWN-AU``
    A reference points at a row that does not exist.
``SDMD-REGIME-AU``
    A constraint names a regime that belongs to another AU.

The fixture in ``tests/fixtures/sdmd/`` has two AUs and ten plots and validates
cleanly. It is the contract that later tasks reuse.

Ingestion
---------

The adapters in ``ws4.sdmd.ingest`` take a DataFrame and return a typed contract
table. They do not read a proprietary file format and do not fetch data; the
caller is responsible for obtaining the public source under its licence.

.. code-block:: python

   from ws4.sdmd.ingest import (
       label_synthetic,
       leading_species,
       match_plots_to_aus,
       read_lidar_evidence,
       read_psp_plots,
       read_psp_trees,
       read_vri_aus,
   )

   plots = read_psp_plots(raw_plots)
   trees = read_psp_trees(raw_trees, plots=plots)
   aus = read_vri_aus(raw_vri)
   species = leading_species(trees)
   result = match_plots_to_aus(plots, aus, leading_species=species)
   matched, unmatched = result.matched, result.unmatched
   lidar = read_lidar_evidence(raw_lidar)

``read_psp_plots`` and ``read_psp_trees`` accept the canonical column names and a
small set of short aliases, coerce the types, and refuse a schema or domain
finding. ``read_vri_aus`` requires one row per AU with a BEC/TSA key, a species
group, and optional age and site-index windows.

``match_plots_to_aus`` fills a blank ``au_id`` only when exactly one AU matches on
region, BEC, TSA, species group, age, and site index. No match and more than one
match go to ``unmatched`` with a ``match_reason``; neither is guessed. A
preassigned ``au_id`` is kept only when the VRI table contains it.

``label_synthetic`` prefixes the source with ``synthetic:`` and sets the review
status to ``provisional``. ``read_psp_plots`` refuses a row that names ``nemora``
without that label, so a gap-fill cannot enter as an observation.

``read_lidar_evidence`` accepts piece size, clump fraction, canopy cover, and a
total TPH. A row whose ``tph_basis`` is ``canopy_only`` may carry structure, but a
TPH on such a row is refused: canopy-derived density is not total stand density.
The basis is a closed set, and every row must carry at least one metric.

Evidence roles and limits
-------------------------

PSP supplies total TPH, basal area, QMD, height, and age support. VRI supplies AU
identity and species composition. LiDAR supplies piece size, crown structure,
and clump evidence. Canopy-only LiDAR is never total TPH, and ``nemora`` is a
labelled gap-fill rather than an observed source.

The classic diagram assumes even-aged, healthy, untreated development. Selection
regimes are flagged as outside the diagram, not plotted as valid paths. The
provincial atlas, legal-compliance determination, a new growth model, and an
AFRF calibration without enough plots are out of scope.
