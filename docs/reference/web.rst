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
   * - ``GET /api/runs/{run}/map?year=&layer=treatments``
     - A GeoJSON ``FeatureCollection`` of the blocks treated in the year, joined to ``--geometry``.
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
       stopping criterion.
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

Geometry
--------

The compiled dataset carries block attributes and areas but not polygons. ``--geometry`` names a
GeoJSON file of block points or polygons with a ``block_id`` property; the map joins on it. Without
one, the map endpoint refuses with a 409 that names the missing option rather than returning an empty
map.

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
table (first 200 rows) and opens HTML/PNG reports directly. Standard reports are the run's own files;
nothing is recomputed in the browser.

Front end
---------

The browser application and the four skin manifests (model builder, scenario analyst, scenario
browser, reviewer) are specified in ``notes/design/ws4-web-frontend.md``. A skin is a JSON manifest
over one application, checked against a registry; an unknown panel, layer or action is refused by
name, and a read-only skin cannot edit a target.
