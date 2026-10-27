Web service (optional)
=======================

The ``web`` extra serves the artefacts a run already wrote over HTTP, for the browser front end
(phase P18). It is a **reader**: every response is a file the CLI produced — the dataset manifest, a
run's summary, its account values, its reports, its schedule — or the targets YAML the optimizer
reads. The service computes no value the CLI cannot reproduce.

.. code-block:: bash

   pip install 'ws4[web]'
   ws4 serve --dataset build/compiled --runs runs --targets targets.yaml \
             --geometry blocks.geojson

The bind is ``127.0.0.1`` by default and a non-loopback address is refused unless ``--allow-remote``
is passed; no authentication is provided in this cut. Starting a search is a separate permission:
``POST /api/runs`` is refused unless ``--allow-runs`` is given, and the command is composed by the
service from the dataset and targets it was started with — the request body can choose only the
iteration count, the seed, the horizon, the number of parallel islands and an optional time limit.
The service may also be started with ``--topology``, ``--patch-accounts``, ``--spread-accounts``,
``--block-coordinates`` and ``--route-config``; those inputs are handed to every search it starts, so
a web-started optimizer run can write the same patch membership and spatial reports as the CLI.
The islands are independent starts in a process pool: ``islands: 8`` uses eight workers, and the
run's summary is the best of them. The iteration count is **per island**, so a bounded run of
``iterations: 1000`` with eight islands performs up to eight thousand iterations in total.

A run is a **solver session**: the browser's **Solve** starts a continuous search (or one bounded by the
iterations or time entered), **Pause** writes ``{"action": "pause"}`` to the run's control file, and **Stop**
writes ``{"action": "stop"}``. The optimizer polls that file every sixty-fourth iteration, so a stop
still produces the usual schedule and summary rather than a killed process. The event stream is
coalesced to one progress record, one targets snapshot and the merged schedule diff per poll, which
keeps a fast search from flooding the page. With parallel islands it follows the island with the
lowest objective; ``progress`` carries the aggregate step count in ``total`` and names that island,
and a schedule event with ``reset`` replaces the client's map when the best island changes. A
progress record also carries the current solution's objective and the accepted-move count, so the
run panel shows activity while the incumbent is flat. Whole-schedule solvers emit the target and
schedule snapshots as well, at the same twentieth-iteration cadence as the incremental solver, so
patch, route, spread, and edge runs animate the map and target cards during the search. Each
worker writes its own ``telemetry-<island>.jsonl`` while it runs; the run's canonical
``telemetry.jsonl`` is merged from them after the search, and the live reader follows the worker
files so it sees the search at the solver's rate rather than behind one writer.

Browser shell
-------------

The browser shell is organised around four workspaces:

- **Map** — layers, treatment/cumulative views, and block detail.
- **Plan** — the account browser, target editor, and solve controls.
- **Results** — Reports, Compare, and Search as nested sections.
- **Data** — the dataset summary plus LiDAR and Carbon when the selected run/dataset
  actually has them.

The **Map** workspace uses a neutral fill for untreated blocks and a red accent for treated
blocks, so treatment reads as the subject and the estate remains visible as context. An
on-map legend names the current layer and repeats the treated/untreated counts from the
sidebar; its **Treated only** button hides untreated blocks without losing the legend. The
legend follows the active view (A/B/both comparison, base attribute, cumulative earlier
periods, or the LiDAR scale). Clicking a block adds a dark outline and fills the detail
panel; the outline is available in both MapLibre and the SVG fallback. **Map engine** and
**Unavailable layers** are compact disclosure rows, not active controls.

The supported planning surfaces start at **1024×768 in landscape**, including the iPad
Pro landscape sizes; phone layouts are not a supported target. The primary navigation
fits inside the sidebar at those widths and the sidebar width scales with the viewport
instead of staying at a fixed 30 rem. Saved splitter widths are clamped to the current
viewport.

Run, workspace, sub-section, period, and selected block are reflected in the URL
(``?run=…&view=…&sub=…&period=…&block=…``), so refresh and browser back/forward restore
the view. The workspace tabs implement the WAI-ARIA tabs pattern with left/right arrow,
Home, and End navigation. LiDAR and Carbon are nested Data sections rather than top-level
tabs; a Data option is hidden when the selected data does not exist.

Assistant panel
---------------

The assistant panel and its drag splitter are rendered only when the service was started
with ``--allow-agent`` **and** the ``opencode`` binary is available. Without both, the panel
is absent and occupies no vertical space; the rest of the sidebar uses the recovered height.
The browser cannot enable the assistant, because doing so would change the service's execution
permissions. Start a separate service with ``--allow-agent`` when the assistant is wanted.

Behind a proxy
---------------

A hosted notebook environment often publishes a local port under a URL prefix, for example a
JupyterHub proxy path of the form ``/user/<name>/proxy/8000/``. Pass that prefix as ``--root-path`` so
the generated links and the OpenAPI pages resolve, and open the prefixed URL rather than the bare
port:

.. code-block:: bash

   ws4 serve --dataset build/compiled --runs runs --root-path /user/me/proxy/8000

The browser application uses **relative** URLs for the API and its assets, so the same build works at
``/`` and under a prefix. The proxy must forward long-lived responses for the SSE stream; a proxy that
buffers the whole response will hold the stream until the run ends.

Endpoints
---------

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Endpoint
     - Returns
   * - ``GET /api/summary``
     - The dataset manifest and the runs found under the configured root.
   * - ``GET /api/runs/{run}/summary``
     - The run's ``summary.json``.
   * - ``GET /api/runs/{run}/accounts?year=&account=``
     - Rows of the run's ``account_values.csv``, filtered.
   * - ``GET /api/lidar``
     - The dataset's registered FEMIC LiDAR pin, licence, CRS, products, and canonical
       ``lidar_*`` block fields. Each field carries its dataset-wide valid count and min/max;
       ``total_blocks`` is the full block table, not the map viewport. ``available`` is false
       for a dataset without LiDAR.
   * - ``GET /api/runs/{run}/carbon``
     - Carbon provenance, ``carbon.*`` account series, pool composition, flux series,
       ledger status, GCBM comparison rows, and artifact names. Pools and fluxes are summed
       by timestep; ``available`` is false when the run has no carbon artifacts.
   * - ``GET /api/runs/{run}/dhi?format=json|geojson``
     - DHI source metadata, band names, and normalized block values. ``format=geojson``
       joins the values to ``--geometry``; without geometry it is a 404. ``available``
       is false when the run has no DHI artifacts.
   * - ``GET /api/runs/{run}/reports``
     - The run's report files and their sizes.
   * - ``GET /api/runs/{run}/reports/{name}``
     - One report file; a name the run does not hold is a 404.
   * - ``GET /api/runs/{run}/map?year=&period_start=&layer=&account=&format=&bbox=&zoom=&lidar=``
     - A GeoJSON ``FeatureCollection`` joined to ``--geometry``. ``year`` is the period's end year
       and ``period_start`` its first year, so ``treatments`` covers the period; ``cumulative``
       marks the current period and earlier ones, ``patches`` carries the year's patch membership,
       ``compartments`` the model spread membership (one ``account`` at a time), and ``blocks`` is
       the bare geometry. ``format=wgs84`` transforms the geometry for MapLibre; the default is the
       source CRS the SVG uses. ``bbox=minx,miny,maxx,maxy`` keeps only intersecting features, in
       WGS84 when ``format=wgs84``. ``zoom`` below 10 returns block centroids; for treatment layers
       it returns only treated centroids, and for the bare block layer it returns an even sample.
       The response carries ``total_features``, ``total_treated``, ``total_untreated``, and
       ``overview_mode`` so the shell can keep full-run counts while drawing the viewport.
       ``lidar=true`` joins the dataset's canonical block LiDAR fields by ``block_id`` and sets
       the response's ``lidar`` flag.
   * - ``GET /api/runs/{run}/tiles/{z}/{x}/{y}.mvt?year=&layer=&period_start=``
     - One Mapbox Vector Tile for ``blocks``, ``treatments``, or ``cumulative``. The layer is
       named ``blocks`` in the tile. Below zoom 6, treatment layers carry treated block polygons
       only; at zoom 6 and above they carry every intersecting block polygon. Tiles below zoom 8
       use ``--geometry-overview`` when it is configured; detail zooms use ``--geometry`` and
       simplify only to the tile resolution. The response is cached in memory and on disk and is
       marked ``Cache-Control: public, max-age=3600``.
   * - ``GET /api/geometry/bounds?format=``
     - The configured geometry's extent as ``[west, south, east, north]``, in the source CRS or
       WGS84. The MapLibre shell uses it to fit the view to the AOI even when the service has no
       land-base layer.
   * - ``GET /api/runs/{run}/compare-stats?against=&year=&period_start=``
     - The full-run A-only, B-only, both, and neither counts for two runs, without reading geometry.
   * - ``GET /api/runs/{run}/compare-tiles/{z}/{x}/{y}.mvt?against=&year=&period_start=``
     - One MVT tile whose ``compare`` property is ``a``, ``b``, ``both``, or ``none``. The Compare
       map uses the same vector source and colors those flags directly.
   * - ``GET /api/runs/{run}/map-stats?year=&layer=&period_start=``
     - The full-run ``total_features``, ``total_treated``, and ``total_untreated`` for the layer,
       so a tiled viewport keeps the run's own counts.
   * - ``GET /api/runs/{run}/layers``
     - The layers the run can actually draw (treatments, cumulative, patches, compartments), its
       patch and compartment classes/accounts, and the named reasons roads/used roads/compartments
       are unavailable.
   * - ``GET /api/runs/{run}/periods``
     - The run's own range: min/max and distinct years from its schedule, patch membership or
       account values, the configured targets' period width, and the folded periods (``start``,
       ``end``, ``label``) the map control steps through.
   * - ``GET /api/runs/{run}/used-roads?year=&format=``
     - The route model's used segments for one year as GeoJSON ``LineStrings``, from the run's
       ``used_roads.csv``; a run without the artifact is a named 404. ``format=wgs84`` for MapLibre.
   * - ``GET /api/roads?format=``
     - The configured source access-road lines as a GeoJSON ``FeatureCollection`` for the map
       overlay; a service started without ``--roads`` returns a named 404. ``format=wgs84`` for
       MapLibre.
   * - ``GET /api/targets``
     - The targets YAML as written.
   * - ``PUT /api/targets``
     - Validate with the optimizer's loader and replace the YAML; an invalid document is refused and
       the file is left unchanged.
   * - ``GET/PUT /api/targets.json``
     - The parsed targets as JSON, for an editor that does not parse YAML.
   * - ``GET /api/runs/{run}/targets``
     - Each target's realized value over the target's own period — the optimizer's
       ``period_value`` rule: a product sums its offsets, a feature reads the period's end offset.
   * - ``GET /api/runs/{run}/target-series``
     - Every target account's bounds, active state, and target indices by run period, plus the
       run's period list. Inactive targets are included. The Plan chart canvas consumes this
       contract and adds achieved values from the run's account series.
   * - ``POST /api/runs``
     - Start a search with the configured dataset and targets. **Refused unless the service was started
       with ``--allow-runs``**; iterations and years are bounded. With no ``iterations`` (or ``0``) the
       run is **continuous** until stopped; a blank or zero **Max iters** field sends this default.
       A positive ``iterations`` is the per-island budget, and ``patience`` (default 0, off) stops
       after that many iterations without an incumbent improvement. The body may also carry
       ``time_limit``, ``seed``, ``years`` and ``islands``; a time limit is applied only when given.
   * - ``POST /api/runs/{run}/control``
     - ``{"action": "pause" | "run" | "stop"}``. The search polls its ``control.json`` every 64
       iterations: pause holds it, and stop returns its best schedule so the run writes its summary.
   * - ``GET /api/runs/{run}/events``
     - SSE: coalesced ``progress``, ``targets`` and ``schedule`` events, then ``done`` with the run's
       own summary, or ``error``. For parallel runs it follows the best island and reports the
       aggregate step count; a ``targets`` event carries the folded period values and the tracked
       accounts' yearly series. A finished run returns **204 No Content**, which stops an EventSource
       from reconnecting; a live stream closes after ten minutes and reconnects, so a lost browser
       cannot leave a stream holding a thread.
   * - ``GET /api/skins``, ``/api/skins/{id}``
     - The checked skin manifests.

LiDAR
-----

The **LiDAR** tab is read-only. It shows the registered bundle id, version, source, licence,
native CRS, products, and the canonical block field catalog. Selecting a field colours the
visible blocks from the Parquet block values and uses the field's **dataset-wide** min/max, not
the range of the current viewport. A coverage badge reports valid blocks over the full block
table, and the legend names the unit and missing-value treatment; the on-map legend repeats the
same scale and coverage. The palette is a colour-blind-safe viridis ramp, and missing or
out-of-coverage blocks stay neutral grey. Clicking a block adds all its LiDAR values to the
detail panel. The layer deliberately uses the explicit GeoJSON join instead of the MVT shortcut,
because MVT properties do not carry the LiDAR fields. A dataset without a registration keeps
the tab visible with a compact unavailable state.

The source must be a P52-registered FEMIC LidarBC bundle; the browser does not open rasters,
reproject them, or derive new terrain or canopy values.

Target charts
-------------

The **Plan** workspace opens a Patchworks-style chart canvas instead of the map. Pinning a
target row (the watch checkbox in the target table) opens one chart per account. Each chart
shows every run period on the x axis:

- red minimum zone;
- blue maximum zone;
- grey acceptable band when both bounds exist;
- black achieved line and status-coloured points;
- an exact readout for the hovered/selected period;
- an expandable all-period table with period, min, max, achieved, and status.

Inactive targets are charted as indicators with a dashed card, not hidden. The chart updates
from the same SSE target snapshots that drive the live map, so the achieved line moves while
the solver runs. Clicking a period selects it in the shell; the period hit element is the
selection authority, so a click anywhere inside the visible column selects that column. The
selected period is highlighted.

Each chart is also an editor:

- toggle the target account active/inactive;
- choose minimum or maximum and type an exact value;
- drag vertically on the chart to set the selected bound;
- apply to the selected period or to all periods;
- clear a bound without deleting the indicator row;
- save through the validated targets JSON path.

"All periods" creates a target row for each period that has no row yet, using the account's
period width and the existing weights/priority as defaults. A save reloads the targets, chart,
and table together; invalid bounds are refused by the same loader the optimizer uses. The target
table remains the editor for weights, normalization, priority, and notes.

Carbon
------

The **Carbon** tab reads the P58 artifacts without running libcbm. It shows the package id,
libcbm version, carbon units, CBM defaults version, package fingerprint, schedule hash, and the
carbon ledger when one exists. Account names are rendered as human labels with inferred
``tC``, ``tCO2e``, or per-year units. The selector draws the run's own offset/value series on a
chart with labelled year and value axes; hovering, focusing, or tapping a point shows the exact
year and value, and the latest year is repeated above the chart. Pool composition is the latest
timestep of the aggregated biomass, DOM/soil, and product groups, with compact ``tC`` amounts
and an accessible colour per group. Raw ``carbon_*`` and GCBM comparison files remain available
through the reports endpoint. A carbon-only run is selectable even though it has no schedule or
map; its period range comes from ``carbon_accounts.csv``. A run without carbon keeps the tab
visible with a compact empty state instead of an empty chart frame.

Layers
------

The Legend tab builds a grouped tree from ``GET /api/runs/{run}/layers`` and the run's own files:

- **Current period** and **cumulative through period** come from ``schedule.csv``; the map control
  folds offsets by the configured targets' ``period_width`` and shows both the period and its year
  range. The previous/next period is one click on the slider or one **left/right arrow key**;
  cumulative distinguishes the current period (red) from earlier ones (tan).
- **Patch size class** comes from ``patch_membership.csv``. A run without a schedule still gets a
  period range from the patch membership, or from its account values, so a simulate run can be read.
- **Spread compartments** comes from ``spread_membership.csv``: the untreated blocks grouped into
  connected components over the run's fast edges. The layer colours each component by its area class
  (0–10, 10–50, 50–150, 150+ ha), numbers the largest component 0, and draws the period's treated
  blocks as breaks. When the run has more than one spread account, the layer tree offers the account
  selector. This is a **model** layer, not the source ``COMPART`` base colour.
- **Current period** is a solid fill; **earlier** cumulative treatments use a diagonal hatch.
  Patch classes are distinct solid colours. Polygon boundaries stay stroked, so the stand mosaic is
  visible at every zoom.
- **Base colour** is a presentation choice over the source attributes: compartment, THEME2, THEME5,
  MartStrata or LMU. The select shows a colour legend for the categories; the map colours every
  block by the chosen source field. This is a static, source-derived view, not a model computation,
  and every layer keeps the same polygon geometry.
- **Access roads (source)** is an optional overlay from ``--roads``, a GeoJSON of the source
  access-line layer. It is a static source network.
- **Used roads (run)** is the route model's used segments for the selected year, from the run's
  ``used_roads.csv``. It is served by ``GET /api/runs/{run}/used-roads?year=...`` and is distinct
  from the source overlay; a run without the artifact names it unavailable rather than drawing
  the source network as if it were used. A run without ``spread_membership.csv`` likewise keeps
  **Spread compartments** unavailable rather than inventing membership.

MapLibre
--------

The browser shell can render the same layers with **MapLibre GL JS** (vendored in
``static/vendor``, BSD licensed) and an OpenStreetMap raster basemap. The layer tree and period
controls are unchanged; the **Map engine** group switches between MapLibre and the SVG fallback.
MapLibre requests the map, source-road and used-road layers with ``format=wgs84``; the service
transforms the source CRS with pyproj. Start the service with the CRS the geometry actually uses:

.. code-block:: bash

   ws4 serve --dataset build/compiled --runs runs --geometry blocks_full.geojson \
     --geometry-overview blocks_overview.geojson --crs EPSG:26911

``--geometry`` is the detail layer; ``--geometry-overview`` is an optional coarser layer used by
tiles below zoom 8. Without the overview, every zoom uses the detail layer. Add ``--tile-cache PATH`` to keep the MVT tiles across restarts. Tiles are written under
``PATH/<run>/<layer>/year-<year>/period-<start>/<z>/<x>/<y>.mvt`` and served with
``Cache-Control: public, max-age=3600``. The response header ``X-WS4-Tile-Cache`` reports
``memory``, ``disk``, or ``miss``. Without the flag the cache is in memory only.

The SVG fallback keeps native coordinates and remains available when WebGL or the basemap is
unavailable. The basemap is an external OpenStreetMap raster source; without network access the
blocks still draw, but the basemap is blank. MapLibre draws the cumulative earlier-period fill as
a flat tan rather than the SVG hatch; the API and layer semantics are otherwise identical.

MapLibre requests the current viewport with ``bbox`` and ``zoom`` and reloads after a debounced
``moveend``. Below zoom 10 the service returns compact centroids; treatment layers return the
treated blocks only, and the bare block layer returns an even sample. At zoom 10 and above the
service returns the intersecting block polygons. The shell keeps the full-run treated/untreated
counts from the response while the map draws only the viewport. This keeps a management-unit map
from loading every polygon up front.

The shell uses the MVT tile endpoint for the block, treatment, and cumulative layers. The vector
source requests only the tiles MapLibre needs at the current zoom. Below zoom 6, treatment layers
show treated block polygons; at zoom 6 and above they show every block polygon. The tile layer is
named ``blocks`` and its properties carry ``block_id``, ``treated``, and ``current``. Low-zoom
tiles use the configured overview geometry; detail zooms use the full geometry and simplify only
to the tile resolution (50 m below zoom 9, 15 m at 11-12, 5 m at 13-14, and full at 15+). The shell
reads full-run counts from ``map-stats``. Patches and compartments stay on the GeoJSON path,
where the per-feature styling is richer; comparison uses a dedicated compare MVT tile.

Pre-warm and deployment checks
------------------------------

The durable cache can be warmed before the first browser request:

.. code-block:: bash

   python scripts/prewarm_tiles.py \
     --dataset runtime/tsa46_full/matrix \
     --runs runtime/tsa46_full/runs \
     --geometry runtime/tsa46_full/fragments.geojson \
     --geometry-overview runtime/tsa46_full/fragments.geojson \
     --tile-cache runtime/tsa46_full/tile-cache \
     --bbox=634372,684898,1029161,1222796 \
     --zooms 0-7 --layers blocks,treatments,cumulative \
     --period-width 10 --horizon 100

The report names tiles requested, failures, bytes, seconds, and the durable-cache
header counts. The command opens the app in-process with the same cache directory,
so the service then serves the warm tiles from disk. Add ``compare`` to ``--layers``
and ``--compare-against RUN`` to warm the comparison tiles for a run pair; the compare
cache is stored per pair and period.

The compare browser smoke needs two completed runs::

   python scripts/check_compare_browser.py http://127.0.0.1:8017/ \
     --run-a baseline --run-b opening_first

It selects the pair, asserts that compare tiles are requested, and checks the A/B/both
counts and the target Kind column. The compare benchmark measures the first cold tile,
the full cold pass, and the warm pass::

   python scripts/benchmark_compare.py http://127.0.0.1:8022/ \
     --run-a web-20261024-221127-1 --run-b web-20261025-032849-2 \
     --zoom 9 --bbox=-114.75,49.62,-114.13,50.40

It fails when the first cold or warm tile exceeds its budget. On c5 (six tiles at z9)
the recorded first tile was 2.063 s cold and 0.003 s warm; the full cold pass was
13.336 s, the warm pass 0.018 s.

The path-prefix check mounts the service at ``/ws4`` and requests the shell, its
static assets, the API summary, a viewport map, and an MVT tile through the prefix:

.. code-block:: bash

   python scripts/check_map_proxy.py \
     --dataset runtime/tsa46_full/matrix \
     --runs runtime/tsa46_full/runs \
     --geometry runtime/tsa46_full/fragments.geojson \
     --prefix /ws4

It also asserts that the shell and script use relative URLs, which is what makes a
path prefix work without a rewrite rule.

The browser path has an opt-in map-hierarchy smoke. It checks the neutral fill, selected
outline, on-map legend, treated-only toggle, compact unavailable layers, and the 1024,
1194, and 1500 px layouts::

   python scripts/check_map_hierarchy.py http://127.0.0.1:8022/ --run run-dated3

The data panels have an opt-in smoke that needs one LiDAR service, one carbon service, and an
empty service (c5 or TSA 46). It checks dataset-wide coverage, the viridis palette, the carbon
axes/tooltip/labels, and the compact unavailable states::

   python scripts/check_data_panels.py \
     --lidar-url http://127.0.0.1:8026/ \
     --carbon-url http://127.0.0.1:8028/ --carbon-run ws4-tsa46-gcbm-baseline \
     --empty-url http://127.0.0.1:8029/

The browser path has an opt-in smoke:

.. code-block:: bash

   python scripts/check_map_browser.py http://127.0.0.1:8000/

It needs Playwright and a Chromium build, and it fails when the shell makes no ``.mvt`` request or
reports a console error. It is not a CI gate because the browser install is heavy.

The targets path has a separate opt-in smoke. Run it against a service started with a
**scratch** copy of the targets YAML, because it adds and then removes a target:

.. code-block:: bash

   python scripts/check_target_browser.py http://127.0.0.1:8021/ --search CWH_HW_M

It opens the Targets tab, filters the account tree, adds a target with the first
matching account, checks that the table gained a row, and removes that row when the
file still has another target. The last target is left in place because the API
refuses an empty targets document.

The Solve and Stop controls have a separate smoke. It needs a service started with
``--allow-runs`` and a scratch targets file, because it starts a short run:

.. code-block:: bash

   python scripts/check_run_controls.py http://127.0.0.1:8022/

It clicks Solve with the default blank **Max iters**, asserts that ``POST /api/runs`` returns
200 with ``continuous: true`` and no time limit, and the button moves to Pause; it then clicks Stop. The SVG and MapLibre shells share these controls; the check
guards against the regression where the click listener was only installed by the SVG
map path.

The scale gate builds a synthetic point grid and times the tile path:

.. code-block:: bash

   python scripts/benchmark_map_scale.py --fragments 1000000 --check

The check fails when a zoom-0 or zoom-12 tile is over 2 MB, the cold request is over 120 seconds,
the warm request is over 5 seconds, or peak RSS is over 4096 MiB. On 2026-10-24, 1,000,000 fragments
produced a 130 KB zoom-0 tile in 25.19 seconds cold and 0.018 seconds warm, a 2.8 KB zoom-12 tile in
0.034 seconds, and a peak RSS of 1,734.6 MiB. The bare block layer is sampled to at most 5,000
features below zoom 6, which is what keeps the zoom-0 tile bounded.

Geometry
--------

The compiled dataset carries block attributes and areas but not polygons. ``--geometry`` names a
GeoJSON file of block points or **simplified block polygons** with a ``block_id`` property; the map
joins on it. Without one, the map endpoint refuses with a 409 that names the missing option rather
than returning an empty map.

The browser shell renders polygons as SVG paths with their boundaries visible, so the stand mosaic
is not reduced to points. The service parses the geometry once and reuses it for every layer; the
response carries the polygon geometry and the source properties. A ``compartment`` property, when
present, is shown in the block detail.

Prepare a simplified polygon layer from the source ``blocks.shp`` with the ``geo`` extra:

.. code-block:: python

   import geopandas as gpd
   import pandas as pd

   frame = gpd.read_file("blocks.shp")
   frame["block_id"] = pd.to_numeric(frame["BLOCK"], errors="coerce").astype(int)
   frame["compartment"] = frame["COMPART"].fillna("").astype(str)
   frame["theme2"] = frame["THEME2"].fillna("").astype(str)
   frame["theme5"] = frame["THEME5"].fillna("").astype(str)
   frame["strata"] = frame["MartStrata"].fillna(-1).astype(int).astype(str)
   frame["lmu"] = frame["LMU"].fillna("").astype(str)
   frame = frame[["block_id", "compartment", "theme2", "theme5", "strata", "lmu", "geometry"]]
   frame["geometry"] = frame.geometry.simplify(5.0, preserve_topology=True)
   frame.to_file("blocks_polygons.geojson", driver="GeoJSON")

The 5 m tolerance keeps the stand boundaries while cutting the vertex count by roughly two thirds;
the coordinates stay in the source projection. Pass the resulting file to ``--geometry``. A point
layer remains valid.

Skins
-----

Four manifests ship: ``model-builder``, ``scenario-analyst``, ``scenario-browser`` and ``reviewer``.
They are served at ``/api/skins`` (and ``/api/skins/{id}``). A manifest selects panels, layer families
and actions; an unknown panel, layer or action is refused by name when the service starts, and a
read-only skin may not carry a mutating action. The browser applies the manifest by hiding panels and
disabling the target editor; the rule lives on the server, so a client cannot enable what the manifest
does not list.

Comparison
----------

The **Compare** tab reads two completed runs through the existing reader endpoints and a
compare-tile endpoint. At the selected year the map colors blocks treated only in A, only in B, and
in both; the vector tile carries the flag in its ``compare`` property, and the full-run counts come
from ``compare-stats``. The target table shows each target's kind, period value and status for both
runs, the ending-inventory table compares the final feature values from each run's summary, and the
account table lists the per-account delta ``B − A``, sorted by absolute change and filterable. The
report tables appear before the map request finishes, so a large AOI does not hide them. The server
computes nothing new: the target values use the same ``period_value`` rule, and a run with no values
at the year is named rather than silently shown as zero everywhere.

Chat agent
----------

The lower-left chat panel is an embedded `OpenCode <https://opencode.ai>`_ coding agent. It runs
the installed ``opencode`` CLI with the model named by ``--agent-model`` (default
``opencode-go/deepseek-v4.1-flash``). The CLI's own login supplies the provider key; WS4 does not
read or store it. The agent works in ``--agent-cwd`` (default: the service's directory), so it can
read the repository, run ``python -m ws4.cli`` commands, inspect a run, and edit files when asked.

.. code-block:: bash

   ws4 serve --dataset build/compiled --runs runs --targets targets.yaml              --allow-runs --allow-agent

This is a deliberate, separate permission and is **off by default**. The agent runs with the
service user's filesystem and shell permissions and auto-approves its own tool calls; anyone who
can reach the service can therefore ask it to change files or run commands. Keep the service on
loopback (the default) or behind an authenticating proxy, and do not enable it on a shared service.
The panel keeps one OpenCode session per conversation and starts a new one with **New**; a session
id is lost on reload, so a fresh page starts a fresh conversation. A horizontal drag bar above the
panel resizes its height (8 rem minimum, leaving the layer panel usable); the height is kept in
local storage, and double-clicking the bar restores the default.

Targets
-------

The Targets tab starts with every account the selected run reports in
``account_values.csv``. The tree folds the account name on its ``.`` segments, and
the search box filters the tree by substring, so a user can find an account without
knowing its exact name. Each leaf shows the account's last realized value, whether
the optimizer treats it as a **level** or a **flow** (a ``product.`` account is a
flow), and a ``target`` badge when the account already appears in the targets file. The
full account name is shown; the count beside the search box reports matches over the
catalogue. Enter selects the first match, and the arrow keys move between leaves.

Selecting a leaf opens a small form for a new target. **Period** is the accounting
period (period 1 is the first one), **Width** is its length in years, and **Min** and
**Max** are optional bounds; the form requires at least one bound. Turn on
**Multi-select** to choose several accounts; the shared period/width/bounds form adds one
target per selected account in a single validated save. Duplicate account/period targets,
missing bounds, min above max, and invalid priorities are refused in the browser before
the request. The table's **Target period** column is the optimizer's one-based period; the
map control labels its periods by year range, so the two clocks are not confused. The table
shows **P1**, **P2**, and so on for per-period rows and **All** for a whole-horizon row, with
the ending year underneath and the full period description in the title.

The target table is a compact view of the same document. Account names are shortened to
their path below the root (for example **Yield · managed · Conifer**), with the root shown as
a small badge and the full path in the title. Units are inferred from the account name where
the name is unambiguous — ``ha``, ``m³``, ``%``, ``tC``, and ``tCO2e`` — and are left blank
rather than guessed. A **Status** column shows **met**, **below min**, **above max**, **off**,
or a dash for no achieved value, and updates from live run snapshots. The achieved value
stays as a secondary line under the account.

Click the **On**, **Account**, **Target period**, **Min**, **Max**, or **Status** header to sort
the view. A second click reverses the direction and **File order** restores the YAML order.
Sorting moves only the rendered rows, so unsaved edits and the original target indices are
preserved; saving after a sort writes the same document order. At 1024 px the table switches to
fixed compact columns so the status remains visible; the account title still carries the full
path.

Each target has a second, compact line with **Min w** and **Max w** penalty weights,
**Normalization** (``none`` or ``auto``), **Priority** (a positive integer tier), **Kind**
(``level``, ``flow.even``, or ``flow.ndy``, derived from the flow setting), and **Notes**.
**Add target** validates the complete list through ``POST /api/targets.json``, writes the
configured YAML, and refreshes the table. The form defaults the width to the width already
used by the file, or ten years when the file is empty. The run controls — Save targets,
Solve/Pause/Stop, the live detail, and the status lines — are sticky at the bottom of the
sidebar, so a long targets table does not hide the controls.

The table's **Remove** button deletes one target through the same endpoint. The API
refuses an empty targets document, so the last target must be removed in the YAML or
with ``Put targets``; the button is disabled in that case. The account browser only
changes the targets document; it does not change account values or the optimizer's
semantics.

The editor writes the document with ``yaml.safe_dump``. It preserves each target's
``notes`` field, but comments and the original key order are not preserved. Before replacing
the file, the service copies the previous document to ``targets.yaml.bak``. Use a
version-controlled targets file and review the diff after a large edit.

Search artifacts
----------------

The **Search** tab lists directories under the runs root that hold a ``portfolio.json``,
``tuning.json``, ``lp_sensitivity.json``, or ``lp.json``. A portfolio shows its members, objective,
declared metrics, status, failures, and which members are on the Pareto front. Selecting a member
shows its factors, metrics, and safe download links for the schedule, targets, ``front.csv``,
``portfolio.md``, and ``console.log``. A tuner shows its ranked candidates, best/median, failures,
and parameters. An LP artifact renders target duals and option reduced costs, labelled advisory.
The file endpoint resolves only paths under the artifact directory. When the service has
``--allow-runs``, the tab also starts a portfolio or tuner
through ``POST /api/search/portfolio`` or ``POST /api/search/tune`` and polls
``GET /api/search/{name}/status``; the endpoint runs the existing ``scripts/portfolio.py`` and
``scripts/tune.py`` against the configured dataset and targets. A running job has a **Stop** control; the
status reports `stopping`/`stopped`. The in-memory job list is bounded and drops the
oldest finished entries. A read-only service shows only the artifacts.

Reports
-------

``GET /api/runs/{run}/reports`` lists the report files a run wrote. The application renders a CSV in a
table (first 200 rows) and opens HTML/PNG reports directly. The Reports tab groups the named
**standard reports** when present — account summary, target status, route cost (overall and per
destination), patch accounts and metrics, spread metrics, edge contrast, the road network, the
schedule and the ending inventory — and keeps the full file list below them. The ending-inventory
card shows the final feature values and year from ``summary.json``, plus any flow-target status.
Nothing is recomputed in the browser.

Runs written before the current clock schema carry ``year`` in ``account_values.csv`` and ``period``
in ``schedule.csv``. The shared run-table reader adds an ``offset`` alias for either column and keeps
the existing ``year`` label, so the Accounts, Periods, Targets, and Map endpoints open the legacy run
instead of returning a 500. The files are not rewritten.

The **Build a report** form selects accounts (comma-separated, or blank for all) and a year range
from the run's own ``account_values.csv``, renders the rows, and exports the same rows as a CSV
download. A target's **On** checkbox is written through the same save as the bounds: an inactive
target stays in the YAML, is shown as ``inactive`` in the target report, and is not priced. The
target table and watched cards use the same active flag.

Front end
---------

The browser application and the four skin manifests (model builder, scenario analyst, scenario
browser, reviewer) are specified in ``notes/design/ws4-web-frontend.md``. A skin is a JSON manifest
over one application, checked against a registry; an unknown panel, layer or action is refused by
name, and a read-only skin cannot edit a target.
