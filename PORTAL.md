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

## Public service

The service is loopback-only by default. Put it behind the same nginx front end as
the other demos if exposing it publicly. The agent has shell/filesystem access
through the configured instance working directory; do not expose it without the
usual trusted-proxy decision.
