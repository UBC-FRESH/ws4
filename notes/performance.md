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

Both are well under the 0.2 s-per-year target.

### Parallelism: threads vs processes

The obvious "use the 72 cores" move is thread-level parallelism. Measured on the C5 numeric core, it
does **not** pay:

| Approach | Time (per year of account values) | vs the current loop |
| --- | ---: | ---: |
| Current per-curve `numpy.interp` loop | 5.8 ms | 1.00× |
| Threads (4 / 8 / 16) over the curve loop | — | **0.35× / 0.29× / 0.23×** (slower) |
| Fully vectorized multi-curve interpolation (disjoint-domain searchsorted) | 18.0 ms | 0.32× (slower) |

`numpy.interp` holds the GIL and the per-curve work is small, so threads serialize and add overhead;
the vectorized single pass allocates many full-size temporaries and loses to 1 114 small interps. The
numeric core is already at the practical numpy floor. Threads do help one GIL-releasing path —
parallel parquet reads in simulator construction (52.6 ms → 29.6 ms, 1.78×) — but that is ~5% of
construction, which happens once per run.

The effective parallel lever is therefore **process-level** (the island model in
`ws4/opt/engine.py`), not threads: independent searches and evaluations run in worker processes, and
the island model migrates the global elite between episodes. This is recorded so the thread idea is
not re-tried without cause.

### P6.4 incremental objective evaluation

WP4 first removed the per-evaluation waste: one reusable `Simulator` (reset instead of rebuilt),
per-curve arrays in `apply_treatments`, a memoized destination choice per (block, product), a route
ledger summary mode, and a vectorized fragment-to-feature join. Then it made the objective itself
incremental.

Feature account values are **additive over blocks** (fragments evolve independently), so a schedule's
account values are the empty-schedule base plus a per-block delta:

```
values(schedule) = base + sum over scheduled blocks of (treated_block - empty_block)
```

The optimizer caches the base once and each block's delta (lazily, per assignment), so an evaluation
is a few hundred dictionary additions rather than a full multi-year re-simulation. Edge contrast and
route accounts are not additive over blocks, so those configurations fall back to the full
simulation.

| Metric (C5, 10 years) | Before WP4 | After |
| --- | ---: | ---: |
| Warm objective evaluation, empty schedule | 1.29 s | 0.23 s |
| Warm objective evaluation, 300-block schedule | 3.8 s | **0.0067 s** (6.7 ms) |

Parity with the full simulation holds to floating-point tolerance (cell-wise max difference ~3e-8),
covered by `tests/test_optimizer.py`. The target (under 50 ms) is met for the account-value objective;
the route/edge configurations keep the full path.

### Shared age-grid curve table (spike, `spike/shared-grid`)

Every offset is an integer age and every curve breakpoint is an integer, so each curve is precomputed
at every integer age once (`ws4/sim/curve.py:CurveTable`), turning curve evaluation into a 2-D gather.
`account_values` uses one gather; `_curve_value`, the patch/edge criteria, and the per-block
trajectories use the same table (with the `numpy.interp` fallback for a non-integer age).

| Metric (C5) | Before | After |
| --- | ---: | ---: |
| `account_values`, per year | ~11.9 ms | **2.33 ms** (5.1×) |
| Base simulate, 30 years (warm) | 0.376 s | **0.095 s** (3.9×) |
| Base simulate, 30 years (cold, incl. join build) | 0.376 s | 0.266 s |
| Construction | 0.52 s | 0.57 s (+~12 MB table) |

Two findings from the spike: an inefficient table build (per-curve masking) made construction slow
until it was rewritten as one sort-and-slice; and `Simulator.reset` was invalidating the
fragment-to-feature join on every call, so the empty-schedule simulate paid a 0.13 s rebuild —
`reset` now invalidates only when the tracks actually changed. Plan and full log:
`notes/design/ws4-curve-grid.md`.

### Fast fragment-to-feature join rebuild (`spike/join-rebuild`)

The join rebuild that dominated the cold path used `np.unique` over ~210 k **string** labels. Since the
features table never changes, its side of the join is now precomputed once (sorted feature rows with
each curve's table row and label code), and a rebuild is a `searchsorted` plus a vectorized expansion.

| Metric (C5) | Before | After |
| --- | ---: | ---: |
| One join rebuild | 0.127 s | **0.0045 s** (28×) |
| Cold 30-year simulate | 0.299 s | **0.129 s** (2.3×) |
| Warm 30-year simulate | 0.102 s | 0.096 s |

Plan and log: `notes/design/ws4-join-rebuild.md`.
