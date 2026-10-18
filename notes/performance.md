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

### Incremental route accounts (`spike/inc-route-accounts`)

Route accounts (haul, maintenance, volume) are additive over blocks like feature accounts, so they
join the incremental objective; only **build** cost is not (charged once per segment across the
schedule) and keeps the full path. `Simulator.block_route_accounts` computes one block's routed
accounts in isolation, reusing the summary ledger for consistency.

| Metric (C5, route-target config, 10 y) | Before | After |
| --- | ---: | ---: |
| Warm evaluation, 300-block schedule | 93.0 ms | **14.2 ms** (6.5×) |
| First evaluation (cold, builds the per-block deltas) | 604 ms | 1871 ms |

The first evaluation is slower (it builds the per-block route deltas); a search amortizes it across
its iterations. Plan and log: `notes/design/ws4-incremental-route-accounts.md`.

### Faster simulator construction (`spike/construction`)

Construction built a per-curve sorted x/y cache (`_curves`) that, after the age table, was used only as
the non-integer-age fallback. `CurveTable.value` now serves any age (exact at integers, linear between
them, clamped), so `_curves` is gone.

| Metric (C5) | Before | After |
| --- | ---: | ---: |
| Simulator construction | ~0.55 s | **~0.15 s** (3.7×) |

Plan and log: `notes/design/ws4-construction.md`.

### Faster route-record accumulation (`spike/route-record`)

The reporting ledger's `record` did per-segment dict work once per produced product. It now aggregates
`(volume, count)` per `(year, destination, route)` and does the per-segment pass once per route at
flush time (volume summed, haul linear in volume, maintenance per record, build once).

| Metric (C5, 3-year, 300-block, collect=True; warm) | Before | After |
| --- | ---: | ---: |
| `simulate` + reporting | ~0.78 s | **~0.08 s** (10×) |

Plan and log: `notes/design/ws4-route-record.md`.

### Adjacency-scoped spatial constraints (`spike/incremental-spatial`)

The optimizer's spatial penalty scanned every topology edge on each evaluation (166 ms for a 300-block
C5 schedule). Only edges incident to a disturbed block can contribute, so an adjacency index lets an
evaluation scan `schedule x degree` edges instead.

| Metric (C5, 300-block schedule) | Before | After |
| --- | ---: | ---: |
| `_spatial_penalty` | 163.7 ms | **13.1 ms** (12.5×) |

Penalties are identical (parity test vs the full-edge computation). Plan and log:
`notes/design/ws4-spatial-scoped.md`.

### Faster matrix builder (`spike/builder-perf`)

The builder re-parsed the recipe's huge constant `lookupTable(...)` literals on every evaluation (once
per stratum per attribute). The parsed form is now cached by the identity of the keys string; token
expansion skips texts with no `%`; and each stratum's matching selects are memoized.

| Metric (MKRF canonical recipe) | Before | After |
| --- | ---: | ---: |
| Build, 200-fragment slice | 17.7 s | **2.2 s** (8.1×) |
| Build, 1 763 fragments (full canonical) | 192.7 s | **21.5 s** (9.0×) |

Outputs are identical (`scripts/acceptance.py` `compare_matrix`: MATCH). Plan and log:
`notes/design/ws4-builder-perf.md`.

### P7.2 the `threads` setting, applied and measured

`OptimizeConfig.threads` was documented as "the number of BLAS and worker threads for single-process
work" and nothing read it: the command line passed its value to `workers` and the field itself had no
effect. It is now applied wherever an optimizer is built, which is the parent and every worker
process. Two mechanisms are needed. The environment (`OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`,
`MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS`) covers libraries loaded later and
is inherited by children, but a **forked worker inherits its parent's already-initialised BLAS**, so
setting the environment in the child is too late to matter; `threadpoolctl` retunes the pools already
loaded in the process, which is what actually pins a worker. It is now in the `opt` extra and in
`requirements-dev.txt`; without it the environment is still set and the configuration still records
the request.

Does pinning matter? No, and that is worth recording so nobody re-tries it:

| Measurement (C5-class binding workload, 4 000 iterations/island) | BLAS threads per process | Throughput |
| --- | ---: | ---: |
| One island | 1 | 1 037 iterations/s |
| One island | 8 | 1 033 iterations/s |
| 32 islands, round 1 | 1 | 13 660 iterations/s |
| 32 islands, round 1 | 64 (effectively unpinned) | 12 318 iterations/s |
| 32 islands, round 2 | 1 | 14 385 iterations/s |
| 32 islands, round 2 | 64 | 15 877 iterations/s |

The pinned and unpinned rounds overlap, so the search neither gains nor loses from BLAS parallelism —
consistent with the earlier finding that the curve loop holds the GIL.

Island scaling, measured at a host load average of 3.9 (essentially idle) at the start:

| Islands | Wall | Throughput | Speedup |
| ---: | ---: | ---: | ---: |
| 1 | 3.769 s | 1 061 iterations/s | 1.0x |
| 8 | 6.395 s | 5 004 iterations/s | 4.7x |
| 32 | 9.193 s | 13 924 iterations/s | 13.1x |

So the criterion "near-linear scaling to 32+ cores" stands as met **with a limit**: 13x to 16x on 32
islands. The limit is not the BLAS pools (the A/B above) and not the per-process setup (~1 s: dataset
load, candidate chains, patch state). It is contention: the machine's load average moved between 4
and 65 across the session's runs, and the rounds above differ by ±15% at the same setting. A scaling
figure from this host is only meaningful with its load recorded, which is why both tables carry it.

### P8.2 the C5 figures, reproduced from the documented commands

The Phase 6 acceptance figures were measured interactively, so Phase 8 re-ran them from the commands
now written in `docs/reference/performance.rst`, on the same 72-core host, at a load average of 4.65
at the start. The sample is the one the lab maintains, which is not in the repository; that is now
stated in the documentation, along with what it must contain.

| Figure | Recorded (Phase 6) | Re-run (Phase 8) | Difference |
| --- | ---: | ---: | --- |
| C5 30-year `simulate` | 0.108 s | 0.113 s | +5% |
| C5 3-year `simulate` + routing, 300 blocks | 0.685 s | 0.576 s | -16% |
| Patch accounts, per year, amortised over 30 years | 29 ms | 28 ms | -3% |
| Edge contrast, 30 years | 1.157 s | 1.147 / 1.251 s | +-5% |
| One full objective evaluation | 0.681 s | 0.500 - 0.754 s | within noise |
| Fragments in the compiled sample | 16 174 | 16 174 | exact |
| Peak resident memory | 496 MB | 487 - 504 MB | +-3% |

Everything reproduces within the noise of a shared host, and the one count that must be exact is. No
figure has drifted in a way that needs restating; the timings vary by a few percent between runs at
the same load, which is the reason each table records the machine and the load it was taken at rather
than a single number to be trusted to three decimals.

### P8.4 island scaling, measured at a known load

P7.2's scaling figure came from a host whose load moved between 4 and 65, so Phase 8 re-measured it on
the same binding C5 workload (a volume floor plus a patch ramp, 4,000 iterations per island, one thread
each) with the load recorded for every run. The machine is two sockets, 18 cores each, two threads per
core — **36 physical cores** — and the load average sat between 5 and 9 for the runs below except where
noted.

| Islands | Wall | Throughput | Speedup | Efficiency | Load before -> after |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 3.79 s | 1,055 it/s | 1.0x | - | 5.0 -> 5.1 |
| 4 | 4.94 s | 3,238 it/s | 3.1x | 77% | 8.8 -> 8.8 |
| 8 | 5.32 s | 6,014 it/s | 5.7x | 71% | 5.1 -> 5.6 |
| 16 | 6.79 s | 9,432 it/s | 8.9x | **56%** | 8.3 -> 9.5 |
| 18 | 6.11 s | 11,782 it/s | 11.2x | 62% | 9.5 -> 13.2 |
| 32 | 6.85 s | 18,685 it/s | **17.7x** | 55% | 5.6 -> 10.6 |

Two things fall out of this.

**The criterion is met with a limit, and the limit is memory.** Efficiency is already down to ~56% at
16 islands — half the physical cores — so the cause is not what the earlier notes suspected:

- **not the BLAS pools**: pinning them changes nothing (P7.2 measured 1 037 against 1 033 iterations/s
  on one island, and pinned against unpinned rounds overlapping at 32);
- **not the per-process setup**: it is about 1 s against 4-7 s of search per island here;
- **not SMT or CPU oversubscription**: 16 processes on 36 physical cores has no sibling sharing at all,
  and the CPU accounting says each process holds roughly one core (at 32 islands, 185 s of user time
  against 6.85 s of wall, and the same ~6.3 s of CPU per island as a solo run).

What is left is the memory hierarchy: the per-process rate falls from 1,055 iterations/s solo to about
584 at 32 islands *while every process stays busy*, which is the signature of bandwidth and
last-level-cache contention — and with two sockets, of traffic crossing between them. **More islands
still win in absolute terms** (32 islands do 18,685 iterations/s against 1,055 for one), so the limit is
about the shape of the curve, not about whether to use the machine.

**A concrete reason a shared dataset would not stay shared.** The obvious next experiment is one copy
of the dataset for all the workers instead of one each. Worth knowing before trying it: a forked worker
inherits its parent's memory copy-on-write, but the simulator **writes** to the fragments frame it
inherits (`self.fragments["offset"] = ...` on every run), which forces the pages to be copied. So a
shared or mmapped dataset has to come with a read-only simulation state, or the copying happens anyway.

### P9.1/P9.2 sharing the dataset across the pool: measured, and rejected

P8.4 left a hypothesis and an obstacle. The hypothesis was the memory hierarchy; the obstacle was that
every worker builds its own copy of the dataset before it can search, so a forking pool *could* share
one. This is the cheap version of that attempt, the measurement that judged it, and its removal.

**What a worker costs to start**, measured on the C5-class sample:

| Step | Time | Peak RSS added |
| --- | ---: | ---: |
| `Optimizer.from_dataset` | 7 ms | 0 MB |
| `optimizer.simulator()` | 195 ms | +63 MB |
| `optimizer.candidates()` | 539 ms | +90 MB |
| `optimizer.patch_model()` | 243 ms | +18 MB |
| **total** | **~0.98 s** | **~170 MB** |

So a 32-island run builds about **5.4 GB** of private state that looks like it could be shared.

**The attempt.** `Optimizer` touched those caches before creating a worker pool, on the reasoning that a
forked child inherits them copy-on-write. The reasoning about fork is correct, and was verified directly
— a child that calls the *inherited* optimiser's methods reports 174 MB shared and 2 MB private, against
about 65 MB of private pages when it loads its own. **But that probe measured a path the worker never
takes.** A worker does not use the parent's optimiser at all: `_island_job` calls
`Optimizer.from_dataset(Path(dataset_dir), cfg)` and builds its own, caches and all. The parent's work
is inherited, shared, and unused.

**What that costs, measured.** The preload is a *serial* setup in the parent, and the workers reload
anyway, so its whole cost lands on the critical path. Measured directly: 0.789 s. Predict against the
control curve and it lands within ~1% of what the pairs show:

| Islands | Search alone | Predicted with the preload | Observed, shared vs control |
| ---: | ---: | ---: | --- |
| 16 | 5.41 s -> 11,830 it/s | 6.20 s -> 10,324 it/s | median **-12.2%** over 3 pairs |
| 32 | 6.78 s -> 18,870 it/s | 7.57 s -> 16,904 it/s | median **-12.7%** over 3 pairs |

Pairs were run with the order alternated (ABBA), because a first pass that always ran the control first
inherited a host load climbing from 5 to 16 and produced the same ~10% "regression" from load alone —
a confound worth recording, since it is exactly the artefact this kind of measurement invites. At one
island, where no pool is created, the paired differences are +1.7%, -4.4% and -8.4%: noise, as they
should be, and the internal control that says the 16- and 32-island results are not.

**Verdict: removed.** It shares nothing a worker uses, and costs about 1 s of serial setup — roughly
-12% at 16 and 32 islands. The capacity it saves (about 170 MB per worker) is real but worth nothing on
this host, which has 754 GB of memory and 711 GB free; and capacity is not what P8.4 identified as the
limit. **Sharing pages does not reduce bandwidth**: every process still reads the same bytes, so the
bandwidth contention P8.4 measured is untouched by sharing copies. The route that would make the
workers genuinely share one copy — handing the parent's built state to the pool instead of a dataset
path — is recorded in `notes/backlog.md` as a memory-constrained-host option, with no claim of a
throughput win, because the measurement above does not support one.
