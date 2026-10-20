# The WS4 web front end: design

Status: design for P18 (issue #146). No UI code lands before this note is on `main`.

## Goal and non-goals

A browser surface over **the artefacts the CLI already writes**: the compiled dataset, a run's schedule,
account values, route/patch/spread reports and its summary. Four skins (model builder, scenario analyst,
scenario browser, reviewer) are manifests over one application.

Non-goals for the first cut: a second model, UI-only state, multi-user authentication, a database, 3D
or a full GIS editing suite. The CLI remains the only way to produce a result; the service starts a run
by invoking it.

## The artefact contract

The service reads files; it does not hold state the CLI cannot reproduce.

| artefact | what the UI uses it for |
| --- | --- |
| `dataset.json` / `manifest.json` | dataset identity, schema version, table list |
| `fragments.parquet`, `blocks.parquet` | block attributes, ages, areas; the join for map properties |
| `products.parquet`, `features.parquet`, `accounts.parquet` | the labels a target or layer may name |
| `schedule.csv` | treatments by block and period; the current-period vs cumulative layers |
| `account_values.csv` | realized values per year and account; the targets panel and charts |
| `product_values.csv` | per-event yields, for drill-down |
| `route_cost_report*.csv`, `route_table*.csv`, `network_table.csv` | route reports and road layers (built/used/planned) |
| `patch_metrics.csv`, `patch_accounts.csv` | patch layers and the patch report |
| `spread_metrics.csv`, `edge_metrics.csv` | spatial-account layers and reports |
| `summary.json`, `telemetry.jsonl` | incumbent objective, seed, status, progress |
| `targets.yaml` | read **and write**; the optimizer's own file, round-tripped |

**Geometry is an optional external layer.** The compiled dataset carries block attributes and areas but
not polygons. The service accepts `--geometry PATH` (GeoJSON or Parquet with `block_id` and a polygon);
without it the map uses block centroids from an optional `block_points` table. Geometry is joined on
`block_id`; it is never written back into the dataset.

## The service surface

An optional extra, `ws4[web]` (FastAPI + uvicorn). The core `ws4` install is unchanged.

| method | path | purpose |
| --- | --- | --- |
| GET | `/api/datasets` | configured datasets and their manifest summary |
| GET | `/api/runs` | runs under the configured roots, with summary and status |
| GET | `/api/runs/{id}/summary` | `summary.json` as written |
| GET | `/api/runs/{id}/accounts?year=&account=` | realized values, filtered |
| GET | `/api/runs/{id}/map?year=&layers=` | a GeoJSON `FeatureCollection`; properties are the requested layers |
| GET | `/api/runs/{id}/reports` | the report tree (standard and scenario files) |
| GET | `/api/runs/{id}/reports/{name}` | a report's rows (JSON) plus its CSV/PNG path |
| GET/PUT | `/api/targets` | read or replace the targets YAML; PUT validates by loading it |
| POST | `/api/runs` | start a run from a dataset + schedule + targets; returns its id |
| GET | `/api/runs/{id}/events` | the SSE stream |

The SPA is served at `/`. Default bind is `127.0.0.1`; no authentication in the first cut, and the
service refuses a non-loopback bind unless `--allow-remote` is passed. That refusal is the security
decision: it is a local analyst tool until there is an auth story.

## Streaming contract

One SSE endpoint, `text/event-stream`, with named events:

```
event: progress
data: {"iteration": 1200, "objective": 15758.97, "best": 0.0, "time_limit_reached": false}

event: accounts
data: {"year": 4, "account": "product.Treated.managed.FT", "value": 39999.84}

event: target
data: {"account": "product.Treated.managed.FT", "year": 4, "value": 39999.84, "status": "met"}

event: done
data: {"summary": "summary.json", "status": "ok"}
```

Events are emitted from the search's own telemetry, throttled to at most 2 Hz, and the stream closes
with `done` or `error`. The stream never computes a value the run did not write.

## The skin manifest

A skin is a JSON document, not a route or a fork:

```json
{
  "id": "scenario-analyst",
  "title": "Scenario analyst",
  "panels": ["map", "targets", "accounts", "reports", "comparison"],
  "layers": ["blocks", "treatments", "patches", "roads"],
  "actions": ["start_run", "edit_targets", "save_targets", "export"],
  "read_only": false
}
```

The loader checks every panel, layer and action against a registry; an unknown name is **refused with
the name**, not ignored. `read_only` removes every mutating action, including the target edit. Four
manifests ship: `model-builder`, `scenario-analyst`, `scenario-browser`, `reviewer`.

## Map and period control

- Layers are grouped with visibility and a legend: blocks by a feature/product criterion;
  treatments (current period vs cumulative); patches; spread compartments; roads by built/used/planned.
  The first cut renders block points or polygons from the configured GeoJSON with treated/untreated
  classes; the additional layer families reuse the same map endpoint once their artefacts are joined.
- The period control is the model's own: years are folded by `period_width`, and the label is the period
  the reference uses (period 1 ends at year 10). The UI shows both the period and its year range.
- Selecting a block opens its attributes; selecting a patch or compartment filters the accounts to it.

## Targets

A table and a chart, per account and period: minimum, maximum, weights, shape, and an active toggle.
A watched card spans the run's **whole horizon**, not only the periods that carry a target: the
realized series is drawn for every year, and the band appears only where a target sets a minimum or
maximum. The realized value comes from the incumbent; saving writes the same YAML the optimizer reads,
and the PUT validates it by loading it through `load_targets`, so an invalid edit is refused in the UI
exactly as the CLI would refuse it.

## Reports

Standard reports are rendered from the run's CSVs: account summary, route cost per destination, patch
distribution, spread accounts. A user-defined report is a YAML list of accounts and periods; it selects
columns from `account_values.csv`, never recomputes. Export is the file the run wrote (CSV/PNG), plus a
rendered table.

## Parallel islands

The player sends `islands` (one to 64) with the start request. The service passes it as the CLI's
`--starts` and `--threads`, so a browser run uses the machine rather than one core. Each worker writes
`step`, `targets` and `schedule` records directly to its own `telemetry-<island>.jsonl`, with the
`island` label and a flush per record. A single parent writer was the bottleneck at eight islands: the
workers ran at thousands of steps a second while the displayed counter advanced at hundreds. Writing
locally, and merging the worker files into the canonical `telemetry.jsonl` only after the search,
removes that queue. The event stream follows the worker files, picks the island with the lowest
objective, sends its schedule (a `reset` event when the best island changes) and reports the aggregate
step count in `total`. Pause and stop reach every worker through the same control file, and the
parent's absolute deadline is passed into each worker so a time-limited run stops all of them.

## Chat agent

The lower-left panel is an embedded coding agent, not a canned help window. It calls the installed
`opencode` CLI with `--model <agent-model> --format json --auto` and a preamble naming the workspace,
dataset, targets and the run/year the UI is showing. The CLI owns provider authentication; the
service never reads the key. The endpoint parses the CLI's JSON events into the reply text and a short
list of tool actions, and returns the OpenCode session id so the next turn continues the conversation.
The panel is a thin renderer: escaped markdown, action chips, a New button that drops the session.

The permission is explicit (`--allow-agent`, off by default) because the agent has the service user's
shell and filesystem and auto-approves its tools. This is a local-operator feature; a shared or remote
deployment needs an authenticating proxy and a separate decision. The model is a service setting
(`--agent-model`, default `opencode-go/deepseek-v4.1-flash`) and the working directory is
`--agent-cwd` (default: where the service was started).

## Testing

- API contract tests with `fastapi.testclient` over a small fixture dataset and run.
- Targets round-trip: PUT then `load_targets` yields the same mapping.
- Skin loader: an unknown panel/action is refused by name; `read_only` cannot edit.
- Map endpoint: a requested layer exists in the FeatureCollection properties, and a missing artefact is
  a 404 naming the file, not an empty map.
- UI: a smoke test that the SPA builds and loads the three panel families; browser automation is
  optional and must not gate the core install.

## Decisions

1. **Stack:** FastAPI + uvicorn as an extra, with a **dependency-free browser shell** for the first cut
   (vanilla ES modules and SVG), so the service has no Node build and CI needs no JavaScript toolchain.
   MapLibre + a basemap is the target when WebGL, raster basemaps or large layer counts are needed;
   the shell's layer/tree/period contracts are written so that swap does not change the API.
2. **The service is a reader.** A run is started by invoking the CLI; the service does not import the
   optimizer into the request process, so a crash in a search cannot take the UI down.
3. **Targets are the optimizer's YAML**, not a parallel JSON model.
4. **Skins are manifests** checked against a registry; unknown entries fail loudly.
5. **Geometry is an external layer**, joined on `block_id`, never written back.
6. **Local-only by default**; remote binding requires an explicit flag, and authentication is a later
   phase with its own design.
7. **The SPA is prefix-relative.** The service takes ``--root-path`` for a proxy subpath (a hosted
   notebook often publishes a port under ``/user/<name>/proxy/<port>/``), and the browser uses
   relative API/asset URLs so one build works at ``/`` and under the prefix. The proxy must forward
   long-lived responses for SSE, or the live stream arrives only when the run ends.
