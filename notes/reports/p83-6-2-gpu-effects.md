# P83.6.2 sparse GPU effect engine and batched LNS prototype

Date: 2026-10-30
Worktree: `feature/p83-gpu-search` at the P83.6.2 commit
GPU: NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition
PyTorch: 2.14.1+cu130

## Scope

This is the bounded follow-up to P83.6.1.  It adds a sparse CSR float64 effect table, a
batched gather/subtract/segmented-sum path, and a small best-of-batch LNS search.  The
CPU simulated annealer remains the reference and the fallback.  No target semantics,
optimizer loop, or acceptance rule in the CPU path were changed.

## What was added

- `ws4/opt/gpu_effects.py`: sparse CSR float64 effect rows built through
  `Optimizer._block_deltas`; `move_deltas`, `lns_deltas`, `segmented_delta`, and `gather`
  on torch CPU or CUDA.
- `ws4/opt/gpu_search.py`: a bounded best-of-batch LNS prototype for a single-priority,
  non-spatial, non-patch target set, with an exact device penalty pricer and a
  `check` mode that compares device prices with `IncrementalObjective.delta`.
- `tests/test_gpu_effects.py`: synthetic exactness tests for single moves and 64-row LNS
  batches, including a feature stock cell and two product accounts.
- `tests/test_gpu_search.py`: search exactness, improvement, zero-round, and rejection
  tests.
- `examples/gpu_effects/benchmark_c5.py` and `examples/gpu_effects/search_c5.py`: the c5
  2,000-block slice demo and benchmark path.  `.[gpu]` is now an optional extra.

## Inputs

- Compiled dataset: `c5_compiled` (7,257 blocks, 1,401,074 candidate chains).
- Targets: `targets_balanced_stock79.yaml` (43 targets, 401 target cells).
- Seed: `seed_stage1.csv`.
- Slice: the first 2,000 seed blocks (all selected blocks occur in the seed).  The table
  contains all candidate chains for the slice plus the seed chains when the search needs
  them.

## Effect table

| Quantity | 2,000-block slice |
|---|---:|
| Rows (including empty row) | 456,278 |
| Nonzeros | 1,578,701 |
| Nonzeros/row | 3.47 |
| Target cells | 401 |
| Sparse float64 CSR | 28.7 MB |
| Dense float64 equivalent | 1.36 GiB |
| CPU row build | 9.46 s (48,049 rows/s) |
| Upload | 0.123 s (233 MB/s) |
| Peak VRAM allocated / reserved | 58.3 MB / 79.7 MB |

The 401 columns include the feature stock cell at offset 199 (column 398) and both
`product.Yield.managed.Conif` and `product.Yield.managed.Decid` at every one of their
offsets.

## Exactness

| Path | Moves | Max abs error | Tolerance | Pass |
|---|---:|---:|---|---|
| single, float64 | 4,096 | **0.0** | atol 1e-8 | yes |
| LNS-64, float64 | 1,024 | **4.37e-11** | atol 1e-8 | yes |

The CPU reference is the exact contribution/pending sum from the cached
`IncrementalObjective.contribution` dictionaries.  The unit tests use a synthetic recipe
with `product.Volume`, `product.Biomass`, and `feature.Volume`; the c5 benchmark checks the
full 401-column table.  The batched search has a `check` mode that compares every proposal
in the first batches with `IncrementalObjective.delta`; it is exact on the c5 slice.

## Steady-state benchmark

CPU is the warm contribution dictionary plus pending sum only.  GPU is the sparse gather /
subtract / segmented sum; `kernel` is CUDA-event timing.  The CPU column is generous: it
excludes penalty pricing and cold-cache prefetch.

### Single-block moves (2 effect rows per move)

| Batch moves | CPU moves/s | GPU moves/s | GPU speedup | Kernel speedup |
|---:|---:|---:|---:|---:|
| 1 | 269,988 | 1,010 | 0.00x | 0.01x |
| 64 | 190,365 | 26,610 | 0.14x | 0.34x |
| 1,024 | 309,525 | 1,180,205 | 3.81x | 3.94x |
| 4,096 | 320,081 | 4,693,197 | 14.66x | 15.22x |

The sparse path is launch-bound for small single-row batches; this is expected and is why
the prototype batches proposals.

### LNS moves (64 blocks = 128 effect rows per move)

| Batch moves | CPU moves/s | GPU moves/s | GPU speedup | Kernel speedup | GPU rows/s |
|---:|---:|---:|---:|---:|---:|
| 1 | 11,043 | 1,161 | 0.11x | 0.11x | 149k |
| 16 | 4,447 | 18,625 | 4.19x | 4.31x | 2.38M |
| 64 | 4,556 | 72,894 | 16.0x | 16.8x | 9.33M |
| 256 | 4,326 | 289,889 | 67.0x | 69.3x | 37.1M |
| 1,024 | 3,881 | 1,454,740 | **374.8x** | 394.4x | **186M** |

The 1,024-row/64-block case is the largest LNS batch measured.  It moves 131,072 effect
rows in about 0.70 ms of synchronized wall time.

## Batched LNS search

Prototype: 128 independent LNS proposals per round, best proposal accepted under a
Metropolis rule, 500 rounds (64,000 proposals), temperature 1e8 to 1e3.  CPU baseline:
`solve_sa_delta` with the stock `LnsOperator` and 30,000 iterations, same seed schedule.
Both final schedules were re-evaluated from scratch with `IncrementalObjective`.

| Seed | CPU objective | CPU s | GPU objective | GPU s | Search speedup | With build speedup |
|---:|---:|---:|---:|---:|---:|---:|
| 7 | 42,329,754 | 25.84 | **38,497,406** | 8.95 | 2.89x | 1.39x |
| 8 | 45,149,589 | 26.29 | **38,479,739** | 9.08 | 2.90x | 1.40x |
| 9 | 40,935,666 | 24.93 | **37,057,249** | 9.00 | 2.77x | 1.34x |

- Search-only speedup is **2.77-2.90x**, and the GPU objective is better on all three
  seeds.
- A single cold run includes the one-time table build and upload, so it is only
  **1.34-1.40x**.
- Reusing the same table for the three seeds gives
  `9.46 + 0.13 + 27.02 = 36.61 s` against `77.05 s` of CPU search, or **2.10x**.  The
  table is target-specific but reusable across seeds and block slices while the target
  set is fixed.
- Against a **faster CPU variant** that uses the same direct LNS sampling as the GPU
  prototype (not the stock `LnsOperator`), the CPU reaches 37.5M in 22-36 s; the GPU takes
  about 9 s for 37.1-38.5M.  The GPU is 2.4-4.0x faster but is 1-3% worse in objective on
  two of the three seeds.  This is not a strict equal-quality win against that optimized
  CPU variant, so the stock CPU path remains the reference and fallback.

## Interpretation

- The engine is exact and fast for batched LNS; the 1,024-move batch is 375x the CPU
  contribution lookup.
- The batched search is **not** a port of the sequential SA.  It trades one long
  annealing chain for many independent proposals per round.  It improves all three c5
  seeds over the stock reference at 2.8-2.9x search-only, but the quality advantage is
  not uniform against an optimized sequential CPU sampler.
- The one-time build is the remaining cold-start cost.  A production path must persist or
  reuse the table; without reuse the first run is below 2x.
- VRAM is small (58 MB allocated for 456k rows), so several islands can share one table.
- The prototype supports one priority tier and no patch, route, or spatial pricing and
  raises on anything else.  The c5 target set meets those conditions; other scenarios do
  not yet.

## Decision

The sparse engine and batched search are exact and measurably faster in steady state, so
this work is committed on `feature/p83-gpu-search` for cherry-pick.  Do **not** replace the
CPU SA.  The next step, if the phase continues, is table persistence and a wider target
coverage check, not a GPU port of the sequential loop.
