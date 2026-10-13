# WS4 — Wood Supply Simulation System (Spatially explicit)

CLI-first, HPC-ready framework inspired by Patchworks but designed for multi-core Linux environments.
**Key invariants from your dataset & workflow:**

- **PIN files are for launching compiled models, _not_ building them.**
- **Blocks shapefile** is a spatial aggregate of **fragments** and is used at **launch/runtime**, not compile-time.
- **Compilation happens at the fragment level** (tracks, curves, treatments, features/products).
- **Runtime aggregation**: product & feature attributes are summed to the block level on-the-fly.
- **Block treatment operability** = set intersection across a block’s constituent fragments. If fragments differ in eligibility/operability, the block’s available treatment set can be narrow or empty.

> This skeleton favors columnar datasets (Parquet/Arrow), vectorized kernels, and parallel evaluation.

## Quick start

```bash
# (in a virtualenv)
pip install -e .[geo,opt]

# Build canonical dataset (from Patchworks XML + fragments)
ws4 build --xml path/to/ForestModel.xml --fragments path/to/fragments.shp --out build/compiled

# Simulate a given schedule
ws4 simulate --dataset build/compiled --schedule schedules/baseline.csv --years 200 --out out/sim

# Optimize using weighted goal programming (metaheuristic)
ws4 optimize --dataset build/compiled --targets config/targets.yaml --weights config/weights.yaml --threads 32 --time-limit 02:00:00 --out out/runA
```
