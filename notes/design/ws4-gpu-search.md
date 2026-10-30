# GPU-native search design

Phase identifier: P83
Task identifier: P83.6
Parent phase issue: #579
Branch: `feature/p83-gpu-search`
Status: active
Date: 2026-10-30

## Decision

WS4 does **not** need a different mathematical objective, but it does need a different
**execution model** for GPU-scale search. Porting the current one-move simulated
annealing loop to CUDA would retain the sequential acceptance dependency and add kernel
launch overhead. The GPU path should be a batched population/island search with
candidate/effect tensors kept resident on the device.

The current CPU SA remains the reference, the exact repair path, and the fallback.

## Why the current loop is GPU-hostile

- One proposal is evaluated and accepted before the next is generated. There is no
  independent work to fill a GPU.
- The state is a Python dict of `(year, account)` cells; proposals mutate it in place.
- LNS changes a variable number of blocks, so the work is ragged.
- A single block has a handful of fragments and treatment events; the arithmetic per
  move is too small to amortize a CUDA launch.
- The compiled dataset stores curves, not per-block/chain effects.

## GPU-native shape

1. **Candidate effects on the device.** Flatten `(block, chain)` rows into a sparse or
   packed `[rows, target_cells]` tensor. A single move is a row difference; an LNS move is
   a segmented sum of rows. This removes curve evaluation from the inner loop.
2. **Population or islands.** Run many independent solutions (or many independent SA
   chains) concurrently. One CUDA block/warp per solution, or per candidate move.
3. **Batched proposals.** Generate a batch of proposals from the current state, evaluate
   all deltas in one tensor operation, then accept sequentially on the CPU or apply a
   batched selection rule.
4. **Device-resident state.** Keep schedules, totals, and effects on the GPU between
   iterations. Move only summary values to the host.
5. **Asynchronous migration.** For islands, use event-based transfers and delayed
   migration rather than device-wide barriers, as in BrkgaCuda 3.0.
6. **SoA layout.** Structure-of-arrays for per-solution decoding/effect gather; AoS only
   for operators that write one chromosome.

## Candidate search algorithms

- **Batched SA / parallel chains** — closest to the current semantics; multiple chains
  explore independently and the best incumbent is retained.
- **Island BRKGA** — random-key encoding per block; GPU decoding to candidate chains;
  biased crossover and migration. Good for large, rugged discrete spaces.
- **GPU LNS** — bounded neighborhoods evaluated in parallel; one effect-row reduction
  per changed block.
- **GPU A*/beam search** — if a target profile can be expressed as a bounded search with a
  strong heuristic; not the first choice for WS4.

## Recommended first prototype (P83.6)

Do not rewrite the simulator or the objective.

1. Build the candidate effect table on CPU for a bounded c5 slice, verify it against the
   exact evaluator, and load it into PyTorch on the GPU.
2. Implement a **batched delta** operation: gather rows, subtract, reduce.
3. Benchmark 1k/10k/100k rows for single-block and LNS batches.
4. Implement a batch of independent proposals or parallel SA chains.
5. Measure exactness, wall time, VRAM, and host-device transfer.
6. Only then decide whether a BRKGA/cuGenOpt-style population search is the next phase.

## Evidence from the two PDFs

- GPU clustering metaheuristics: one CUDA block per candidate solution and a parallel
  fitness kernel gave an average 175x over CPU.
- BrkgaCuda 3.0: async island migration and removal of device-wide synchronization gave
  4.6x on one GPU and 96.6% weak scaling to eight GPUs; the quality gain came from more
  migrating islands, not GPU count alone.

These support a population/batch execution model, not a one-move GPU port.

## Current c5 baseline

- 100k no-LNS: ~36 s, ~2,770 eval/s end-to-end.
- 1.4M candidate chains; 7,257 blocks; target cells are sparse.
- Full dense CPU effect table: ~44 s build, ~1.8 GB RSS; not worth it for one run, but
  potentially worth it if reused across large-model runs or many seeds.

## Acceptance

- The GPU delta path must match the CPU evaluator on random moves.
- The benchmark must report wall time, VRAM, transfer volume, and objective.
- A negative result is acceptable; it must say whether the limit is launch overhead,
  transfer, table size, or search quality.
- Dashboard green before closing.

## P83.6.1 benchmark result (2026-10-30)

Bounded benchmark: 1,000 blocks / 226,661 candidate chains / 401 target cells, RTX PRO 6000,
torch 2.14.1+cu130.

- Exact CPU effect-row build: 4.29 s (~52,850 rows/s)
- Full-table estimate: 26.5 s build, **2.09 GiB dense float32**, ~44 MB sparse
- Single-block GPU delta: **slower than CPU** (0.03x); kernel launch dominates
- 64-row batch: **2.17x**
- 1,024-row batch: **50x**
- 64-block LNS: **191x**
- 1,024-block LNS: **514x**
- Float32 exactness was not production-grade: max absolute error 0.0059 and max relative
  error 0.0069 on LNS batches. The prototype also computes a float64 table; it needs a
  clean exactness run before use.

Conclusion: the GPU is for **batched effects/LNS/population work**, not single sequential
moves. The next prototype should use float64 or corrected accumulation and a sparse
device representation, then a batched search around the effect rows.

