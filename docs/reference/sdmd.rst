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
space. ``validate_trajectory`` refuses a path where density and mean tree volume
both increase between points: a stand cannot gain trees and stem volume at once.
``assess_trajectory`` returns ``inside`` or ``extrapolated`` and names the first
point outside. ``build_au_report`` combines the observed evidence, the
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

Stand density equations
-----------------------

``ws4.sdmd.equations`` is an independent Python implementation of the density
equations used by the BC stand density management diagrams. It does **not** call,
wrap, or vendor the R application or the ``standview`` package. The equation
forms and coefficients come from the published sources; the unit handling follows
the BC app so the two implementations can be compared.

Sources and ideas:

- The BC Government SDMD Shiny application, `bcgov/SDMD
  <https://github.com/bcgov/SDMD>`_ (Apache-2.0), for the equation-set selection,
  the metric/English conversion path, and the maximum-SDI defaults and ranges.
- The ``standview`` R package by M. W. Ritchie (USFS), `mwritchie/standview
  <https://github.com/mwritchie/standview>`_, for the diagram calculation logic
  that the BC app uses.
- The published equations: Long and Shaw (2005) ponderosa pine; Jang, Ritchie,
  and Zhang (2021) ponderosa pine; Long and Shaw (2012) Sierra Nevada
  mixed-conifer; Drew and Flewelling (1979) Douglas-fir; McCarter and Long (1986)
  lodgepole pine; and Reineke (1933) for the stand density index.
- The static/dynamic/structural framing and the review of SDMD variants:
  `10.1139/cjfr-2020-0289 <https://doi.org/10.1139/cjfr-2020-0289>`_.
- The BC stand density management page, which publishes the diagram set:
  `Stand density management
  <https://www2.gov.bc.ca/gov/content/industry/forestry/managing-our-forest-resources/silviculture/silvicultural-systems/silvicultural-interventions/stand-density-management>`_.

Five equation sets have a complete volume and top-height calculation: 2, 3, 6, 7,
and 9. Each set declares whether it has volume, top height, crown cover, or
biomass, and its maximum-SDI default and range. The public functions take metric
inputs and return metric outputs.

.. code-block:: python

   from ws4.sdmd import (
       basal_area_m2_ha,
       relative_density,
       stand_density_index,
       top_height_m,
       volume_m3_ha,
       volume_isoline,
   )

   volume = volume_m3_ha(3, tph=1000.0, qmd_cm=25.0)
   height = top_height_m(3, tph=1000.0, qmd_cm=25.0)
   sdi = stand_density_index(1000.0, 25.0)
   rd = relative_density(1000.0, 25.0, max_sdi=988.0)
   isoline = volume_isoline(3, target_m3_ha=300.0, tph_values=(500.0, 1000.0))

``stand_density_index`` defaults to a 25.4 cm reference, the 10-inch convention
the BC app uses for its metric maximum-SDI values. Pass ``reference_cm=25.0`` for
the common metric convention. ``volume_isoline`` inverts a volume equation by
bisection on QMD; densities that cannot reach the target are omitted rather than
clipped.

The module's docstrings and the equation registry carry the per-equation
citations. No R code or third-party text is copied into this repository.

AU Explorer API
---------------

``ws4.sdmd.api`` provides a FastAPI router over a directory of the six tables,
an optional ``diagram.json``, an optional ``initial_volume.json``, and optional
``trajectories/<au_id>/<regime_id>.json`` files. The initial-volume file records the
measured value, its evidence limit, the source, and the review status; the gate uses
it when the command line does not supply an override. The main web app mounts it when ``ws4 serve`` receives ``--sdmd-dir``:

.. code-block:: bash

   ws4 serve --dataset build/compiled --runs runs \
             --sdmd-dir data/sdmd

The read endpoints are:

- ``GET /api/sdmd/regions``
- ``GET /api/sdmd/aus?region=...``
- ``GET /api/sdmd/au/{au_id}``
- ``GET /api/sdmd/au/{au_id}/plots``
- ``GET /api/sdmd/au/{au_id}/yield``
- ``GET /api/sdmd/au/{au_id}/sdmd``
- ``GET /api/sdmd/au/{au_id}/regimes``
- ``GET /api/sdmd/au/{au_id}/trajectory?regime_id=...``
- ``GET /api/sdmd/au/{au_id}/constraint-preview``

``POST /api/sdmd/au/{au_id}/constraints`` writes a complete constraint set. The
validator requires one entry per regime for the AU, a matching ``au_id``, valid
field types, the schema limits, and a passing :func:`check_regime` for every
entry. A deliberate ``allowed: false`` is valid; any other finding refuses the
write with ``422`` and leaves the stored set unchanged. A successful write is
atomic and is stored at ``constraints/<au_id>.json``; the next store load reads
it back.

``GET /api/sdmd/au/{au_id}/trajectory`` reads a stored trajectory and assesses it
against the AU's observed envelope. The response carries the stored ``source``,
``scenario``, and ``review_status`` beside the points. When the file is absent, the
response is ``status: "unavailable"`` with a named data gap rather than an invented
path.

AU Explorer tab
---------------

The browser shell gains an optional **SDMD** workspace when the service is started
with ``--sdmd-dir``. It is a reader over the API above, with no build step.

- The left rail chooses a region and AU, filters the yield rows by source, and
  shows the AU's plot count, age support, species, and diagram state.
- The main canvas draws the SDMD isopleths, the observed points, the convex
  envelope, and the selected regime path on logarithmic axes. A legend and a hover
  readout name the curves and the zone. The yield chart has a metric selector
  (volume, density, basal area, QMD, top height) and its own hover readout.
- An interpretation panel states the observed support, envelope range, diagram
  review state, the selected regime's verdict and reasons, the option reduction,
  and the data gaps. It says explicitly when the diagram is an illustrative fixture
  and when a regime has no stored trajectory.
- The constraint editor has one row per regime: allow/deny, entry-age window,
  maximum entries, minimum interval, and maximum removal fraction. Saving posts
  the complete set to the validated endpoint and refreshes the option-count
  preview. A refused save leaves the stored set unchanged.
- ``Use in scenario`` records the AU in the URL for the solver handoff.
- The selected AU and workspace are URL state, so a link opens the same view.
- The trajectory menu lists only regimes with a stored path; the other regimes are
  disabled and labelled "no stored path".

Solver integration
------------------

The optimizer reads the compiled matrix, so the safe integration is to remove forbidden
treatment rows before it builds candidate chains. ``ws4.sdmd.solver.filter_dataset``
reads ``tracks.parquet`` and ``treatments.parquet``, maps each track to an AU from
the ``AU(...)`` field in the track name or a sidecar map, matches each treatment
label to a regime, and drops every treatment row for a track that fails the
constraint checks.

.. code-block:: bash

   ws4 sdmd filter-dataset \
     --dataset build/compiled \
     --out build/compiled-sdmd \
     --regimes regimes.csv \
     --constraints au_constraints.csv \
     --map sdmd-map.yaml

The filter enforces the per-track entry-age window, entry cap, minimum interval,
and removal fraction. It writes a dataset copy with every other table unchanged and
reports ``tracks_before``, ``tracks_after``, ``treatments_before``, and
``treatments_after``, plus one record per dropped track with its reasons. Unmapped
tracks are kept by default; ``--strict`` drops them. A sidecar map can override the
track AU and treatment aliases:

.. code-block:: yaml

   tracks:
     16: AU-IDFdk3-FDI
   treatments:
     CC: REG-A-CLEARCUT

The filter can also enforce the required SDMD zone: pass a diagram and a
trajectory directory, and a track is kept only when its stored trajectory reaches
the constraint's `required_sdmd_zone`. A missing trajectory fails closed.

`SdmdScheduleGuard` checks a whole schedule for the per-AU entry cap and minimum
interval. It maps each block to its AU, counts the selected entries, and returns
`SDMD-SCHEDULE-ENTRIES` or `SDMD-SCHEDULE-INTERVAL` findings. The optimizer wires
it into every move when `--sdmd-dir` names a store with `regimes.csv` and
`au_constraints.csv`; an infeasible seed raises rather than being repaired. The run
summary records `constraint_stats.sdmd_guard` and the number of rejected moves as
`constraint_stats.sdmd_rejected`, which is the enforcement benchmark.

Validation gates
----------------

`ws4.sdmd.validation` runs eight gates for one AU:

1. **Plot support** — at least three observed plots and at least three PSP-backed
   points. Each point must have a reviewed PSP plot at its age and a tree list;
   synthetic points are labelled and excluded from the observed envelope.
2. **Density plausibility** — reported basal area agrees with TPH and QMD.
3. **SDMD fit** — the diagram exists, is reviewed, and the points are inside it.
4. **Trajectory plausibility** — every stored path is physical and assessed against
   the observed envelope.
5. **Initial volume** — the value is supplied and inside the evidence.
6. **Regime completeness** — every regime has a constraint with no unexplained
   finding.
7. **Solver option reduction** — the constraints reduce the option space without
   removing every regime.
8. **UI payload contract** — the detail, yield, SDMD, regime, and preview payloads
   have the keys the tab reads.

.. code-block:: bash

   ws4 sdmd validate --sdmd-dir data/sdmd --au AU-IDFdk3-FDI
   ws4 sdmd validate --sdmd-dir data/sdmd --au AU-IDFdk3-FDI \
     --initial-volume 863 --initial-volume-limit 800

The command exits ``1`` on any failed gate. The fixture warns rather than fails:
its diagram is provisional, it supplies no initial volume, and one demo trajectory
is an extrapolation. The initial-volume tests reject the 863 m3/ha value against
an 800 m3/ha limit and flag 1,173 m3/ha as above the observed maximum.

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

The catalog records the index-page label and the PDF title separately: the BC
page labels `swn`/`swp` as "White pine", but the PDFs are white spruce, and the
catalog keeps "White pine" as an alias so the page label still resolves.

The Farnden 1996 method report (Pacific Forestry Centre Information Report
BC-X-360) is public and is recorded in the catalog with its URL and checksum. The
PDFs are referenced, not copied into the repository. The natural and planted Interior Douglas-fir PDFs are digitised into
``idf-dk3-fdi-natural.json`` and ``idf-dk3-fdi-planted.json``. The natural
lodgepole pine PDF (`pln`, version 1.20) is digitised into
``idf-dk3-pli-natural.json`` with QMD 10-40 cm, top height 6-34 m, the
competition/self-thinning boundaries, and the 60% crown-closure curve. The
planted PDF (`plp`, version 1.20) is digitised into ``idf-dk3-pli-planted.json``
with top height 6-30 m. The real PLI pilot store is
``ws4/sdmd/data/pilot-tsa23-idfdk3-pli/``. The method, curve assignments, and review checklist are in
``notes/reference/bc-sdmd-digitisation.md``. The review packet with overlay figures
for all four diagrams is ``notes/review/p95-curve-review.md``.

The digitisation pipeline uses the public ``figrecover`` package for PDF rendering,
overlay QA, and review manifests, and ``freshforge`` for the workflow graph. The
optional extra installs both:

.. code-block:: bash

   python -m pip install -e '.[digitise]'
   freshforge plan workflows/sdmd-digitise.yaml

The vector-path extractor in ``ws4.sdmd.digitise`` stays responsible for isopleth
precision; figrecover owns the rendered page, overlay, quality metrics, and review
record. A diagram spec names the PDF axis ticks, the drawing path indices, and the
printed isopleth values, so the workflow does not guess curve identities. Both are **provisional** until the
maintainer reviews the curves; the planted top-height assignment is the weaker of
the two. The synthetic ``idf-dk3-fdi-illustrative.json`` remains the test fixture,
not the published diagram. Four method trajectories from `fresh-fvsbc` are in
``ws4/sdmd/data/trajectories/``; they are method runs over synthetic tree lists,
not real AU projections. See ``notes/reference/sdmd-pilot-trajectories.md``.

The CCISS project (Apache-2.0) supplies complementary species evidence: 37 BC
tree species codes, silvics traits for the six SDMD species, IDFdk3 stocking
targets, and the CCISS label table (``bec_crosswalk.csv``). The derived CCISS
files are ``ws4/sdmd/data/sdmd/tree_species.csv``, ``species_traits.csv``,
``idfdk3_stocking.csv``, ``idfdk3_suitability.csv``, and
``idfdk3_sibec.csv``; the method and limits are in
``notes/reference/cciss-data-mining.md``.

The BEC authority tables come from BC BECdb v13, not CCISS:
``bec_official.csv``, ``bec_retired.csv``, and ``bec_sources.json``. P121
derives ``bec_official_crosswalk.csv`` and ``bec_crosswalk_review.csv`` from
those tables; the counts and limits are in
``notes/reports/p121-bec-crosswalk.md``. CCISS does not contain SDMD isopleths,
so it cannot replace the missing lodgepole pine diagram.

All 14 public diagrams are now stored: seven species in natural and planted
versions. Four Interior Douglas-fir/lodgepole pine diagrams are reviewed; the other
ten are provisional and use raster-traced crown closure. The atlas status and BEC
counts are in ``notes/reports/p120-atlas-coverage.md``.

The first real pilot store is ``ws4/sdmd/data/pilot-tsa23-idfdk3/``. It holds 11
reviewed public PSP points for TSA 23 / IDFdk3 / FDI and two FVS paths from the
real tree list of one cluster. Its ``SOURCE.md`` names the BC Data Catalogue
record, the Open Government Licence, the selection rule, the field derivations,
the FVS version, and the limits. The diagram is still provisional, no initial
volume is supplied, and both FVS paths leave the observed envelope; the store is
evidence for the pipeline, not a yield forecast.

BC-wide coverage
----------------

``bec_coverage.csv`` is the 219-row coverage registry. Each current BEC label
names its zone, subzone, variant, applicable Atlas diagrams, species/origin,
review counts, and separate AU evidence. The counts are:

- 1 reviewed BEC label: ``IDFdk3``
- 57 provisional zone-level labels
- 161 labels with no digitized diagram

``GET /api/sdmd/coverage`` returns the registry and filters by zone or status;
``GET /api/sdmd/coverage/{bec}`` returns one label. The SDMD workspace exposes a
**BC coverage** selector. A provisional row is a lead, not an equivalence claim;
a no-diagram row is a named gap. The registry never substitutes an unrelated AU.

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
