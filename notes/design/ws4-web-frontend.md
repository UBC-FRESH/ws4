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

- Layers are grouped with visibility, opacity and a legend: blocks by a feature/product criterion;
  treatments (current period vs cumulative); patches; spread compartments; roads by built/used/planned.
- The period control is the model's own: years are folded by `period_width`, and the label is the period
  the reference uses (period 1 ends at year 10). The UI shows both the period and its year range.
- Selecting a block opens its attributes; selecting a patch or compartment filters the accounts to it.

## Targets

A table and a chart, per account and period: minimum, maximum, weights, shape, and an active toggle.
The realized value comes from the incumbent (`accounts` events). Saving writes the same YAML the
optimizer reads; the PUT validates it by loading it through `load_targets`, so an invalid edit is
refused in the UI exactly as the CLI would refuse it.

## Reports

Standard reports are rendered from the run's CSVs: account summary, route cost per destination, patch
distribution, spread accounts. A user-defined report is a YAML list of accounts and periods; it selects
columns from `account_values.csv`, never recomputes. Export is the file the run wrote (CSV/PNG), plus a
rendered table.

## Testing

- API contract tests with `fastapi.testclient` over a small fixture dataset and run.
- Targets round-trip: PUT then `load_targets` yields the same mapping.
- Skin loader: an unknown panel/action is refused by name; `read_only` cannot edit.
- Map endpoint: a requested layer exists in the FeatureCollection properties, and a missing artefact is
  a 404 naming the file, not an empty map.
- UI: a smoke test that the SPA builds and loads the three panel families; browser automation is
  optional and must not gate the core install.

## Decisions

1. **Stack:** TypeScript + Vite + MapLibre; FastAPI + uvicorn as an extra. No mandatory dependency for
   the CLI.
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
