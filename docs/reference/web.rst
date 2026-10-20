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
iteration count, the seed and the horizon.

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
   * - ``POST /api/runs``
     - Start a search with the configured dataset and targets. **Refused unless the service was started
       with ``--allow-runs``**; iterations and years are bounded.
   * - ``GET /api/runs/{run}/events``
     - SSE: one ``progress`` event per telemetry step, then ``done`` with the run's own summary, or
       ``error``.
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
