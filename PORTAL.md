# WS4 public instance portal

A single FastAPI portal that mounts one WS4 web application per public FEMIC
instance. It uses the same landing-page visual language as the FHOPS public demo.

## Run

```bash
./run_portal.sh
# local: http://127.0.0.1:8790/
# override port: PORT=8791 ./run_portal.sh
```

`WS4_INSTANCES_ROOT` can point at a different `femic/external` directory.

## Engine

The mounted WS4 applications use the resident **state** engine from the
`feature/p84-incremental-state` worktree, not `optimize` and not islands:

- one CPU core
- candidate-index / resident-page search (`ws4 state-watch`)
- final schedule materialised through `ws4 simulate` so the normal WS4 map,
  account, target, and report readers work
- embedded OpenCode assistant enabled on each mounted app

The landing page reports which instances have a compiled WS4 dataset and which
still need a runtime setup. Very large instances are deliberately excluded from
the shared one-core demo.

## GPU readiness

The portal's normal **Run** button is CPU resident-state search for every
instance. GPU capability is separate and is shown on each landing card and by
`GET /api/instances`:

- **GPU profile** — the instance has a scenario-profile library whose profiles
  contain the execution resources needed by `ws4.opt.gpu_profile_run`. TSA 24
  exposes `base`, `baseline`, and `nostock`; TSA 27 exposes `s8`; TSA 29
  exposes `base`. The TSA 27 and TSA 29 profiles use existing effect tables
  without factorized archives.
- **GPU artifacts · CLI** — effect tables exist, but no profile library is wired
  into the portal. These are usable through `ws4 gpu-watch` only after matching
  the dataset, seed schedule, and targets.
- **CPU state-watch** — no effect table or profile resources are installed; the
  CPU resident-state engine is the only search path.

`GET /health` reports counts for `gpu.profile`, `gpu.cli`, `gpu.cpu`, and
`gpu.unavailable`. The readiness check only looks for artifacts and validates
the profile library; it does not start a GPU worker.

## TSA 24 geometry

TSA 24 uses `runtime/geometry/tsa24-blocks.geojson`, derived from the exact
458,708-row public stand shapefile. It is a 5 m simplified, EPSG:3005 layer
with `block_id` from source row order. Low-zoom tiles use
`tsa24-blocks-overview.geojson` at 100 m, and a
`tsa24-blocks.geojson.bounds.json` sidecar lets the map fit without parsing the
detail layer. MVT tiles are persisted under `cache/<slug>/tiles`, so the first
cold low-zoom tile is paid once per cache rather than once per portal restart.
The source hashes and regeneration script are recorded with the layer; the
compiled dataset itself remains geometry-free.

## Public service

`run_portal.sh` binds `0.0.0.0:8790` by default so a container proxy can reach
it; set `HOST=127.0.0.1` for a loopback-only instance. Put it behind the same
nginx front end as the other demos if exposing it publicly. The agent has
shell/filesystem access through the configured instance working directory; do
not expose it without the usual trusted-proxy decision.
