# WS4 — Wood Supply Simulation System (Spatially explicit)

A CLI-first, HPC-ready forest estate model for multi-core Linux environments.

WS4 makes spatial structure part of the model: fragments are the decision units, blocks are a runtime
aggregate, and adjacency, patch structure, and road access are enforced during simulation and
optimization rather than allocated afterwards.

## Key invariants

- **Launch control files start a run; they do not build one.**
- **Blocks** are a runtime aggregate of **fragments**; block geometry is not a compile-time input.
- **Compilation happens at the fragment level** (tracks, curves, treatments, features/products).
- **Runtime aggregation**: product and feature attributes are summed to the block level on the fly.
- **Block treatment operability** is the set intersection across a block's constituent fragments. If
  fragments differ in eligibility/operability, the block's available treatment set can be narrow or
  empty.

The design favors columnar datasets (Parquet/Arrow), vectorized kernels, and parallel evaluation.

## Documentation

- `AGENTS.md` — the working contract for coding agents.
- `ROADMAP.md` — the plan of record and issue tracker map.
- `notes/design/ws4-scope.md` — problem statement, users, scope, and success criteria.
- `notes/design/ws4-architecture.md` — the architecture design.
- `notes/adr/` — architecture decision records.

## Quick start

```bash
# (in a virtualenv)
pip install -e .[geo,opt]

# Build a canonical dataset (from an XML recipe + fragments)
ws4 build --xml path/to/model.xml --fragments path/to/fragments.shp --out build/compiled

# Simulate a given schedule
ws4 simulate --dataset build/compiled --schedule schedules/baseline.csv --years 200 --out out/sim

# Optimize using weighted goal programming (metaheuristic)
ws4 optimize --dataset build/compiled --targets config/targets.yaml --weights config/weights.yaml --threads 32 --time-limit 02:00:00 --out out/runA
```
