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

Diagram and AU report
---------------------

A diagram is a JSON file with ordered vector isopleths, never a raster. The x axis
is trees per hectare and the y axis is mean tree volume; interpolation is linear in
log10 space, which is how the classic diagram is read. ``load_diagram`` validates
the identity, the source, the review record, and every curve before the diagram is
used.

Each diagram needs at least two ``top_height`` curves, at least two ``qmd`` curves,
and exactly one each of ``crown_closure``, ``competition``, and ``self_thinning``.
A ``reviewed`` diagram must name a reviewer and a review time. The maintainer
(G. Paradis) is the reviewer of record for this pilot; an RPF can be named later
without a schema change. An unreviewed or
provisional diagram cannot enter an AU report unless the caller passes
``allow_unreviewed=True`` for method work, and the report records the gap.

.. code-block:: python

   from ws4.sdmd import (
       Trajectory,
       assess_trajectory,
       build_au_report,
       load_diagram,
       observed_envelope,
       place_point,
   )

   diagram = load_diagram("ws4/sdmd/data/sdmd/idf-dk3-fdi-illustrative.json")
   placement = place_point(diagram, tph=1000.0, mean_tree_volume_m3=1.2)
   envelope = observed_envelope([(980.0, 0.757), (2200.0, 0.128), (1700.0, 0.543)])
   assessment = assess_trajectory(
       Trajectory(label="fvs", points=((1700.0, 0.543), (1350.0, 0.793))),
       envelope,
   )
   report = build_au_report(
       au_id="AU-IDFdk3-FDI",
       diagram=diagram,
       observed=points,
       trajectories=(Trajectory(label="ct60", points=ct60_points),),
       initial_volume_m3_ha=500.0,
       initial_volume_limit_m3_ha=800.0,
       allow_unreviewed=True,
   )

``place_point`` names the zone: ``understocked`` below the crown-closure line,
``density-management`` between closure and competition, ``competition`` below the
self-thinning line, and ``outside`` above it or beyond the digitised axis domain.
It also interpolates top height and QMD, and flags a point outside the isopleth
range.

``observed_envelope`` builds the convex hull of an AU's observed points in log
space. ``assess_trajectory`` returns ``inside`` or ``extrapolated`` and names the
first point outside. ``build_au_report`` combines the observed evidence, the
trajectories, and the initial volume into one status: ``supported``,
``extrapolated``, ``rejected``, or ``unsupported``. The initial-volume check
rejects a volume above the supplied evidence limit; an upper-tail trajectory that
leaves the observed envelope is flagged as extrapolation even when the volume
appears in a few old plots.

Regimes and constraints
-----------------------

A regime is a repeated entry, not a one-off schedule. `load_regime_library` reads
the `regimes` table, validates the sequence, and expands `cycle_length` and
`repeat_count` into ordered entry ages. `Regime.entry_ages()` returns the sequence,
`entry_count()` returns the number of entries, and `is_sdmd_valid` is false for a
selection regime. The untreated baseline has no entries and is exempt from the
entry window.

`load_constraints` reads the `au_constraints` table. `check_regime` returns
findings instead of raising, so a caller fails closed. It checks the AU/regime
pair, the allow flag, the entry-age window, the entry cap, the minimum interval,
the maximum removal fraction, and whether a required SDMD zone can be met by a
selection regime. `allowed_regimes` returns only the regimes that pass every
check, and `option_counts` reports the regime and entry counts before and after.

.. code-block:: python

   from ws4.sdmd import (
       allowed_regimes,
       check_regime,
       load_constraints,
       load_regime_library,
       option_counts,
   )

   regimes = load_regime_library(regime_frame)
   constraints = load_constraints(constraint_frame)
   allowed = allowed_regimes(regimes, constraints, "AU-IDFdk3-FDI")
   counts = option_counts(
       tuple(item for item in regimes if item.au_id == "AU-IDFdk3-FDI"),
       allowed,
   )

A forbidden entry never reaches the model: the caller turns a non-empty finding
list into a refusal. Solver filtering itself is P87.7.

Public sources
~~~~~~~~~~~~~~

The BC Ministry of Forests publishes the complete public set as 14 one-page PDFs:
seven species, each in a natural and a planted version. The species are coastal
Douglas-fir, interior Douglas-fir, lodgepole pine, Sitka spruce, western hemlock,
western redcedar, and white spruce. The machine-readable catalog is
``ws4/sdmd/data/sdmd/source_catalog.json``; the BEC zone/subzone/variant coverage
is ``ws4/sdmd/data/sdmd/bec_variants.csv`` (229 rows). The full note is
``notes/reference/bc-sdmd-sources.md``.

The diagrams are species- and origin-based, not BEC-variant-based. The variant CSV
expands the zone-level species occurrence from the BC Tree Species Compendium, so
it is an inference that a forester must confirm against the AU's leading species
and stand origin. For the pilot AU ``IDFdk3`` the diagram is ``fdin`` (natural) or
``fdip`` (planted) for Interior Douglas-fir, with lodgepole pine and western
redcedar as main associates.

The Farnden 1996 method report (Pacific Forestry Centre Information Report
BC-X-360) is public and is recorded in the catalog with its URL and checksum. The
PDFs are referenced, not copied into the repository. The committed
``idf-dk3-fdi-illustrative.json`` is still an **illustrative synthetic fixture**
for the schema and tests; it is not the published diagram and must not be
presented as one.

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
