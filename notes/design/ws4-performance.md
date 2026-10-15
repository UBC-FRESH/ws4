# Performance and scalability plan (post-release)

Status: **planned**, deferred until after the phase 4 initial release (P4). The initial release is
functionally complete but slow on space-and-roads workloads; this note is the plan of record for
making it fast.

Owner: whoever picks up the performance build phase. Evidence: `notes/performance.md` (measured
numbers), `scripts/benchmark.py` (harness), and this note (plan).

Related decisions: ADR 0008 (Python first, native kernels behind a stable API), ADR 0009 (parallel
and GPU execution), ADR 0010 (telemetry-driven tuning and the meta-meta-heuristic portfolio). The
compiled dataset is the contract (ADR 0002, ADR 0006); this plan does not change it except through a
new ADR if a spatial index sidecar is added.

## 1. Why this is the hard part

The simulator, the spatial metrics (patch, core area, edge contrast), and the route model all run
**inside the optimizer's objective**: every candidate schedule is a full multi-year simulation plus
routing plus spatial accounting. The neighborhood moves (toggle, shift, swap, LNS) change one or a
few blocks, so evaluating from scratch wastes almost all of the work. The established model
(Patchworks) runs the same C5 dataset quickly and has for two decades; the algorithm class is
therefore tractable. Our implementation is Python-first and from-scratch, so the first release
trades speed for completeness. This plan closes that gap.

## 2. Current measurements (evidence)

Host: 72 logical cores (2× Xeon Gold 6254), 754 GiB RAM. Dataset: the C5 sample (16 174 fragments,
130 423 curves, 15 558 tracks, 27 231 vertices, 36 721 segments, 3 destinations). Measured with
cProfile and `time.perf_counter` on the spatial+route path:

| Path | Time | Notes |
| --- | ---: | --- |
| `simulate` base, 30 years | ~4.2 s | recorded in `notes/performance.md` |
| `simulate` base, 3 years | 3.6 s | 16 174 fragments |
| `simulate` + edge contrast, 3 years | 6.3 s | `+2.7 s` for `block_criteria` per year |
| `simulate` + routing, 3 years, **300 blocks scheduled** | **61 s** | `assign` + `route` |
| `write_patch_metrics` + patch accounts, 1 year | 2.1 s | full 16 174-fragment replay |
| Optimizer, **one** objective evaluation (C5, warm start, routing) | **~13 min** | end-to-end single iteration |

Hot functions (cProfile, `simulate` + routing, 17.3 s total):

| Function | Cumulative | Why |
| --- | ---: | --- |
| `RouteNetwork._segments_by_id` | 5.95 s (34%) | rebuilds a 36 721-entry dict **on every `route` call** |
| `roads.accounts.RouteModel.assign` | 8.47 s | per produced product |
| `roads.network.RouteNetwork.route` | 7.45 s | includes the dict rebuild and path walk |
| `sim.curve.curve_value` | 3.54 s | scalar lookup per product |
| `sim.engine.apply_treatments` | 16.06 s | pandas `iterrows` + boolean mask per schedule row |
| pandas `__getitem__`/`sort_values` | ~3 s | row-wise access in the simulator |

## 3. Bottleneck map (ranked)

1. **Routing rebuilt per call.** `_segments_by_id` and `_adjacency` are recomputed for every route;
   `assign` runs per product, so 3 664 routes rebuilt a 36 721-entry dict 3 664 times.
2. **Row-wise simulation.** `apply_treatments` iterates schedule rows and fragments with pandas
   `iterrows`/masks; `account_values` is vectorized but treatments are not.
3. **Edge/patch criteria per year.** `block_criteria` does a pandas merge per label per year; the
   edge metric then iterates all 68 586 edges.
4. **Double replay.** `run` simulates once for accounts and replays from scratch in
   `write_patch_metrics` for spatial metrics.
5. **No incrementality.** The optimizer recomputes everything per move; nothing is carried over.
6. **Single-threaded inner loop.** Multi-start uses processes, but each start is one core; 72 cores
   are mostly idle during a search.
7. **Unbounded caches.** Route shortest-path caches and `_segments_by_id`/`_adjacency` rebuilds grow
   or repeat work.

## 4. Strategic plan (what and why)

**Goal:** an optimizer objective that evaluates a C5-class schedule in **tens of milliseconds**, and a
simulation core that runs **≥100× faster** than today, scaling across the 72 cores (GPU where it pays,
per ADR 0009). Reproducibility (seeds, deterministic replay) and the compiled-dataset contract are
non-negotiable.

Five strategies:

- **S1 — Precompute the spatial model once.** Build a compiled *spatial index* (CSR adjacency, block
  geometry: area, perimeter, boundary contribution), and per-destination shortest-path data, once per
  dataset, not per evaluation.
- **S2 — Incremental (delta) evaluation.** Keep objective state; a move updates only the affected
  blocks, years, patches, and route flows. This is the biggest lever because neighborhood moves are
  tiny.
- **S3 — Vectorized, array-based core.** Replace pandas row loops with numpy arrays and precomputed
  interpolation tables.
- **S4 — Parallel and GPU substrate.** Island model with elite migration; batched candidate
  evaluation; NUMA-aware placement; tensorized spatial/curve evaluation where it pays.
- **S5 — Native kernels behind the API.** numba `njit` first, C++ where needed, behind the existing
  Python boundary (ADR 0008), with parity tests.

Cross-cutting: a **benchmark harness and CI performance gate** so the gains are measured and held.

## 5. Tactical plan (how)

- **T1 Dataset caches.** Cache `RouteNetwork._segments_by_id`/`_adjacency` (arrays, not dicts), block
  `area`/`perimeter`, and a CSR adjacency for patch union-find. Optionally persist a spatial-index
  sidecar (new ADR).
- **T2 Array simulator.** Store fragments as numpy arrays (`track_id`, `area_ha`, `offset`, `age`);
  apply a year's treatments with index arrays, not `iterrows`; evaluate curves with a precomputed
  per-curve table and `np.interp` in bulk.
- **T3 Incremental spatial.** Union-find with rollback or a dynamic connectivity structure for patch
  membership; per-block perimeter contributions and core-area closed form; edge contrast as a sparse
  matrix–vector product.
- **T4 Routing.** Compute a shortest-path tree per destination once (or a distance/cost matrix for
  the linked blocks), then a route lookup is O(1); cache bounded and cleared per dataset. Reconsider
  `nearest_destination` as a precomputed per-block best destination when eligibility does not vary by
  product.
- **T5 Solver.** Island model with periodic elite migration; evaluate moves in batches (vectorized
  deltas or candidate-level parallelism); keep the time-boxed budget.
- **T6 Kernels.** numba `njit` for curve interpolation, union-find, and Dijkstra; keep a pure-Python
  fallback for parity and for environments without numba.
- **T7 Harness.** Extend `scripts/benchmark.py` with the C5 spatial+route scenario and per-component
  timings; add a lightweight perf smoke to CI (a generous threshold) and record results in
  `notes/performance.md`.

## 6. Operational plan (ordered work packages)

Each work package is one issue; each has a measurable acceptance criterion. Ordered by leverage.

**WP0 — Harness and baseline (prerequisite).**
- Add a C5 spatial+route scenario to `scripts/benchmark.py` (simulate, routing, patch accounts, edge
  contrast, one optimizer evaluation) and a `--profile` mode.
- Record the baseline table (section 2) in `notes/performance.md`.
- Acceptance: `python scripts/benchmark.py --scenario c5` prints per-component timings; baseline is
  committed.

**WP1 — Route and simulation quick wins (low risk, high yield).**
- Cache `_segments_by_id`/`_adjacency`; array-based simulator for `apply_treatments`; single replay in
  `run`; bounded route caches.
- Acceptance: C5 `simulate` + routing (3 y, 300 blocks) from **61 s → <5 s**; no behavioral change
  (all reference/acceptance comparisons unchanged).

**WP2 — Vectorized simulator core.**
- Array fragments, bulk curve interpolation, vectorized account values and products.
- Acceptance: C5 30-year `simulate` **<1 s**; parity with WP1 outputs on the regression fixture and C5.

**WP3 — Spatial precompute and incremental metrics.**
- CSR adjacency, per-block geometry precompute, closed-form core area, sparse edge contrast, patch
  ledger.
- Acceptance: patch accounts + edge + core per year **<0.2 s** on C5; incremental update is
  `O(changed blocks)`.

**WP4 — Incremental objective evaluation.**
- Maintain objective state; a move updates only affected blocks/years.
- Acceptance: one optimizer move **<10 ms** on C5 (from ~13 min for a full evaluation); objective
  parity with the from-scratch evaluation on sampled schedules.

**WP5 — Solvers at scale.**
- Island model with elite migration; batched/parallel move evaluation; NUMA-aware placement.
- Acceptance: near-linear scaling to 32+ cores on a fixed evaluation budget; best-objective improves
  on the C5 target set.

**WP6 — Native kernels.**
- numba `njit` (then optional C++) for curve interpolation, union-find, Dijkstra, edge contrast.
- Acceptance: parity tests vs the Python path; **≥5×** on the identified hot loops; documented API.

**WP7 — Guardrails and docs.**
- CI perf smoke; determinism/parity tests; update `notes/performance.md`, the design notes, and the
  user-facing performance section.
- Acceptance: perf gate green in CI; reproducibility preserved (same seed → same result).

## 7. Targets (acceptance metrics)

| Metric | Current | Target |
| --- | ---: | ---: |
| C5 30-year simulate | ~4.2 s | <1 s |
| C5 3-year simulate + routing (300 blocks) | 61 s | <5 s |
| Patch accounts + edge + core, per year | ~2 s | <0.2 s |
| One optimizer objective evaluation (C5) | ~13 min | <50 ms (incremental) |
| Parallel scaling | 1 core/start | near-linear to 32+ cores |

## 8. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Incremental evaluation diverges from from-scratch | Parity tests on sampled schedules each WP |
| GPU/native complexity reorders results | Deterministic reduction order; parity tolerance tests |
| Sidecar spatial index breaks the dataset contract | New ADR; sidecar is optional and rebuilt from the parquet |
| Perf work destabilizes correctness before release | This plan is deferred until after P4; the release is correct-but-slow |
| numba unavailable in some environments | Keep a pure-Python fallback behind the same API |

## 9. Explicitly out of scope for the initial release

The P4 release stays **functionally complete but slow**. It documents the spatial+route performance
limits in `RELEASE_NOTES.md` and points here. No optimization work lands before the release merges.

## 10. First three moves (when the phase starts)

1. WP0: extend `scripts/benchmark.py` and record the baseline.
2. WP1: cache the route network internals and vectorize `apply_treatments` (the two cheapest, largest
   wins).
3. WP3/WP4 spike: prototype an incremental patch/route update on a small dataset to validate the
   delta approach before committing to it.
