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

A run is a **player**: the browser's Play starts a continuous search (or one bounded by the
iterations or time entered), Pause writes ``{"action": "pause"}`` to the run's control file, and Stop
writes ``{"action": "stop"}``. The optimizer polls that file every sixty-fourth iteration, so a stop
still produces the usual schedule and summary rather than a killed process. The event stream is
coalesced to one progress record, one targets snapshot and the merged schedule diff per poll, which
keeps a fast search from flooding the page. With parallel islands it follows the island with the
lowest objective; ``progress`` carries the aggregate step count in ``total`` and names that island,
and a schedule event with ``reset`` replaces the client's map when the best island changes. Each
worker writes its own ``telemetry-<island>.jsonl`` while it runs; the run's canonical
``telemetry.jsonl`` is merged from them after the search, and the live reader follows the worker
files so it sees the search at the solver's rate rather than behind one writer.

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
   * - ``GET /api/runs/{run}/reports``
     - The run's report files and their sizes.
   * - ``GET /api/runs/{run}/reports/{name}``
     - One report file; a name the run does not hold is a 404.
   * - ``GET /api/runs/{run}/map?year=&period_start=&layer=&account=``
     - A GeoJSON ``FeatureCollection`` joined to ``--geometry``. ``year`` is the period's end year
       and ``period_start`` its first year, so ``treatments`` covers the period; ``cumulative``
       marks the current period and earlier ones, ``patches`` carries the year's patch membership,
       ``compartments`` the model spread membership (one ``account`` at a time), and ``blocks`` is
       the bare geometry.
   * - ``GET /api/runs/{run}/layers``
     - The layers the run can actually draw (treatments, cumulative, patches, compartments), its
       patch and compartment classes/accounts, and the named reasons roads/used roads/compartments
       are unavailable.
   * - ``GET /api/runs/{run}/periods``
     - The run's own range: min/max and distinct years from its schedule, patch membership or
       account values, the configured targets' period width, and the folded periods (``start``,
       ``end``, ``label``) the map control steps through.
   * - ``GET /api/runs/{run}/used-roads?year=``
     - The route model's used segments for one year as GeoJSON ``LineStrings``, from the run's
       ``used_roads.csv``; a run without the artifact is a named 404.
   * - ``GET /api/roads``
     - The configured source access-road lines as a GeoJSON ``FeatureCollection`` for the map
       overlay; a service started without ``--roads`` returns a named 404.
   * - ``GET /api/targets``
     - The targets YAML as written.
   * - ``PUT /api/targets``
     - Validate with the optimizer's loader and replace the YAML; an invalid document is refused and
       the file is left unchanged.
   * - ``GET/PUT /api/targets.json``
     - The parsed targets as JSON, for an editor that does not parse YAML.
   * - ``GET /api/runs/{run}/targets``
     - Each target's realized value over the target's own period — the optimizer's
       ``period_value`` rule: a product sums its years, a feature reads the period's end.
   * - ``POST /api/runs``
     - Start a search with the configured dataset and targets. **Refused unless the service was started
       with ``--allow-runs``**; iterations and years are bounded. With no ``iterations`` (or ``0``) the
       run is **continuous** until stopped, with a 24-hour safety limit; a positive ``iterations`` is the
       budget, and ``patience`` (default 0, off) stops after that many iterations without an incumbent
       improvement. The body may also carry ``time_limit``, ``seed``, ``years`` and ``islands``.
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

Layers
------

The Legend tab builds a grouped tree from ``GET /api/runs/{run}/layers`` and the run's own files:

- **Current period** and **cumulative through period** come from ``schedule.csv``; the map control
  folds years by the configured targets' ``period_width`` and shows both the period and its year
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

The **Compare** tab reads two completed runs through the existing reader endpoints:
``/api/runs/{run}/map?year=``, ``/api/runs/{run}/accounts?year=`` and
``/api/runs/{run}/targets``. At the selected year the map colors blocks treated only in A, only in
B, and in both; the target table shows each target's period value and status for both runs, and the
account table lists the per-account delta ``B − A``, sorted by absolute change and filterable. The
server computes nothing new: the target values use the same ``period_value`` rule, and a run with no
values at the year is named rather than silently shown as zero everywhere.

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
id is lost on reload, so a fresh page starts a fresh conversation.

Reports
-------

``GET /api/runs/{run}/reports`` lists the report files a run wrote. The application renders a CSV in a
table (first 200 rows) and opens HTML/PNG reports directly. The Reports tab groups the named
**standard reports** when present — account summary, target status, route cost (overall and per
destination), patch accounts and metrics, spread metrics, edge contrast, the road network and the
schedule — and keeps the full file list below them. Nothing is recomputed in the browser.

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
