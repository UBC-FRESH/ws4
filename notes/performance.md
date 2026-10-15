# Performance (P3.5)

The compile and simulate paths are measured with `scripts/benchmark.py` (a synthetic landscape
built from the matrix regression fixture) and with the C5 sample. The host is a 72-core Linux
machine with 754 GiB of RAM.

## Hot paths found

- **Builder: re-parsing per fragment.** The builder evaluated each select statement for every
  fragment and re-tokenized and re-parsed it each time. For 100 038 fragments that was 240 048
  `evaluate` calls and about 10.5 s of a 13.8 s run.
- **Simulator: a per-curve `.loc` setitem.** `account_values` assigned each curve group's yields
  with `merged.loc[group.index, "yield"] = ...`. The C5 model has about 130 423 curves, so that
  setitem dominated the run (about 2.9 s of 4.2 s for five years).

## Fixes

- `ws4/io/expressions.py` caches the parsed tree per statement (`lru_cache`). The tree is built
  from immutable tuples and is never mutated, so sharing it across fragments is safe.
- `ws4/sim/engine.py` assigns yields into a positional numpy array instead of using `.loc` per
  curve group.

## Results

### Synthetic build and simulate (fixture recipe, 10-year horizon)

| Fragments | Build before | Build after | Simulate | Peak RSS |
| ---: | ---: | ---: | ---: | ---: |
| 6 240 | 0.29 s | — | 0.08 s | 128 MiB |
| 24 946 | 1.06 s | — | 0.10 s | 157 MiB |
| 100 038 | 3.79 s | **1.66 s** | 0.26 s | 231 MiB |

The build is roughly linear in the fragment count after the parse cache.

### C5 sample (16 174 fragments, 130 423 curves, 20 151 features)

| Step | Result |
| --- | --- |
| Ingest | 0 validation problems; tracks 1558, strata 3551, treatments 1398, features 20151, curves 130423 |
| Simulate, 5 years | 1.2 s |
| Simulate, 30 years | 15.5 s → **4.2 s** |
| Optimize | one objective evaluation is a full simulate, so the iteration budget must fit the horizon |
| Route | 27231 vertices, 36721 segments, 3 destinations |

## Block aggregation

The simulator aggregates fragments to blocks only where a feature needs it (patch metrics and
routing). At the C5 scale the per-curve yield evaluation dominates, so block aggregation is not
the hot path. The architecture note's open question about a cached incremental block aggregate
is therefore deferred.

## Vectorization

Curve evaluation is vectorized per curve: `account_values` calls `np.interp` once per distinct
curve, not once per fragment
(`tests/test_simulator.py::test_curve_evaluation_is_vectorized_per_curve`).

## Reproduce

```bash
python scripts/benchmark.py --fragments 100000 --years 10
python scripts/benchmark.py --fragments 100000 --years 10 --profile
```

## Space-and-roads baseline (P4)

The spatial and route paths (patch accounts, edge contrast, core area, routing) run inside the
optimizer's objective and dominate the cost. Reproduce the C5 scenario with the harness:

```bash
python scripts/benchmark.py --scenario c5 --sample-dir <sample> \
    --years 3 --route-blocks 300 --spatial-years 1 --workdir tmp/benchmark
```

Recorded baseline (C5 sample; the sample is unpacked outside the repository):

| Component | Time | Notes |
| --- | ---: | --- |
| Ingest | 0.24 s | 16 174 fragments |
| `simulate` base, 3 years (empty schedule) | 0.88 s | |
| `simulate` + edge contrast, 3 years | 3.6 s | |
| `simulate` + routing, 3 years, 300 blocks | 65.4 s | the dominant cost |
| Patch accounts, 1 year | 2.2 s | patch metrics + the size-class sub-accounts |
| One optimizer objective evaluation | 1.3 s | empty schedule; grows with the schedule |
| Peak memory | 2.8 GiB | |

The dominant hot path is route reconstruction (`RouteNetwork._segments_by_id` rebuilt per route) and
row-wise `apply_treatments`. The plan to fix this — profiling, bottleneck map, targets, and the
ordered work packages — is `notes/design/ws4-performance.md`, and the work is phase 6
(`feature/p6-performance`).

### P6.1 route and simulation quick wins

WP1 cached the route-network indexes (built once), precomputed the treatment/product/fragment
lookups, vectorized `apply_treatments` (no pandas `iterrows`), and switched routing to
**per-destination** shortest paths (the graph is undirected, so one Dijkstra per destination serves
every block, instead of one per block).

| Component | Before | After |
| --- | ---: | ---: |
| `simulate` + routing, 3 years, 300 blocks | 65.4 s | **4.5 s** |
| Peak memory (same run) | 2.8 GiB | **338 MiB** |

The one remaining WP1 subtask (a single replay in `run` instead of a second replay for the spatial
metrics) is deferred to WP3, where the spatial pass is restructured for incrementality.

### P6.2 vectorized simulator core

WP2 replaced the per-year pandas merge and groupby in `account_values` with a **precomputed
fragment-to-feature join** (flat arrays of fragment position, curve id, and label code, rebuilt only
when a treatment changes a track) and per-curve `numpy.interp` into a positional array.

| Component | Before | After |
| --- | ---: | ---: |
| C5 `simulate` base, 30 years | 3.76 s | **0.41 s** |
| C5 `simulate` base, 3 years | 0.41 s | **0.15 s** |

The C5 benchmark now times simulator construction separately (about 0.6 s: it loads the parquet
tables and indexes the 130 423 curves), so the component figures exclude it. The current C5 figures:
base simulate (3 y) 0.16 s, edge contrast (3 y) 3.0 s, routing (3 y, 300 blocks) 3.9 s, patch accounts
(1 y) 1.9 s, one objective evaluation 1.2 s, peak memory 372 MiB. The edge contrast and patch accounts
are the WP3 target.

### P6.3 spatial precompute and incremental metrics

WP3 replaced the two spatial hot paths with single passes:

- `block_criteria` (the patch/edge criterion per block) now uses a precomputed per-label join with
  `numpy.interp` and `np.bincount`, instead of a pandas merge and groupby per label per year.
- the patch perimeter is one pass over the edges (an edge with exactly one member end is boundary),
  instead of re-scanning all edges per patch.

| Component (C5) | Before | After | Per year |
| --- | ---: | ---: | ---: |
| Edge contrast, 3 years | 3.0 s | 0.31 s | 0.070 s |
| Patch accounts, 1 year | 1.9 s | 0.25 s | 0.066 s |

Both are well under the 0.2 s-per-year target. The full-history incrementality (an update that touches
only the changed blocks) and the single replay in `run` remain for WP4, where the objective's
evaluation is made incremental.
