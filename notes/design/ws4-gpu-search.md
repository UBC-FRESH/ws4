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

## P83.6.2 end-to-end prototype (2026-10-30)

A standalone 2,000-block c5 slice was built into a sparse-derived **float64** effect table
(456,278 rows, 401 target cells; CPU build 8.1 s). The prototype then ran batched LNS in
two modes:

- 64 independent proposals per batch, best proposal accepted: **5,391 proposal
  evaluations/s**, but only **84 accepted moves/s**.
- 31 disjoint 64-block neighborhoods per batch, accept the improving subset:
  **4,044 proposal evaluations/s**, **179 accepted moves/s**.

The current CPU LNS path is about **1,900 accepted moves/s**. The GPU effect math is not
the bottleneck; acceptance, objective scoring, and neighborhood coupling dominate. A
simple greedy batch is also a poor search: only 137 moves were accepted across 3,100
proposals.

Conclusion: the effect table alone does not make the LNS search faster. The next
prototype must change the search structure (parallel chains/islands with batched
acceptance, or a population search), not just move the current LNS to the GPU.

## P83.6.2 parallel-chain GPU prototype (2026-10-30)

A batched parallel-chain prototype was run on a 2,000-block c5 slice with a float64
effect table (456,278 rows, 401 cells; 8.4 s build):

- 1,024 independent chains
- 50 generations
- 51,200 single-block moves
- **1.30 s steady state**
- **39,451 moves/s**, **38,441 accepted moves/s**
- best objective 2.551B vs 2.602B seed on the slice

This is about **14x** the current c5 CPU no-LNS end-to-end rate (~2,700/s), and unlike the
GPU LNS prototype it keeps the GPU busy with independent work. It is not yet a target
quality result, not integrated into `ws4`, and not scaled to the full dataset. The next
step is to make the chain state/acceptance device-resident and run it on the full model.

### Device-resident chain state

The next prototype kept the K×B chain-row matrix and K×C totals on the GPU, updating only
accepted rows with tensor indexing. On the same 2,000-block slice:

- 1,024 chains, 50 generations, 51,200 moves
- **0.332 s steady state**
- **154,327 moves/s**
- **150,255 accepted moves/s**
- best objective 2.566B vs 2.602B seed
- effect-table build 8.6 s

That is about **57x** the c5 CPU no-LNS end-to-end rate. The table is still a 2,000-block
slice; full TSA23 requires sparse storage and a full candidate/effect build before this is
production-ready.

## P83.6.2 evidence (2026-10-30)

The sparse CSR float64 engine and a bounded best-of-batch LNS prototype were built on the
c5 2,000-block slice.  The full evidence is in
`notes/reports/p83-6-2-gpu-effects.md`.

- Sparse table: 456,278 rows, 1,578,701 nonzeros, 28.7 MB, versus 1.36 GiB dense float64.
- Exactness: single moves max abs error 0; 64-block LNS batches 4.4e-11.
- Steady-state LNS: 1,024 moves x 64 blocks is 374.8x the CPU contribution lookup.
- Batched LNS search: 2.77-2.90x the stock CPU search at better objective on three seeds,
  but 1.34-1.40x for a single cold run because of the one-time 9.5 s table build.  Reusing
  the table across the three seeds gives 2.10x including the build.
- Against a faster CPU variant with the same direct proposal sampler, the GPU is 2.4-4.0x
  faster but 1-3% worse in objective on two seeds.  The stock CPU path remains the
  reference and fallback.

The next step is table persistence and a wider target-coverage check.  Do not port the
sequential single-move loop.

## P83.7 full TSA23 ft_econ scale check (2026-10-30)

Full `compiled_ft_econ` with the 20 x 10-year even-flow target:

- 66,584 candidate blocks
- **20,237,498 candidate chains**
- candidate generation: **72.3 s**
- estimated sparse table: **~1.3 GB** (20.2M row offsets plus ~70M nonzeros), before the
  Python row-index/list overhead
- the current `EffectTable.build` stages all rows and all CPU deltas at once; a full build
  is not yet practical

A 5,000-block subset was built and searched:

- rows 1,590,695; nnz 1,999,367; sparse table **44.7 MB**
- table build **64.5 s**; upload 0.13 s
- GPU search: 2.50 s vs CPU 11.08 s (4.43x), but GPU objective **315.4M** vs CPU **76.5M**
- including the cold table build: **0.17x**
- GPU best-of-batch quality is poor; one accepted proposal per round is not enough

Conclusion: full TSA23 needs a streaming/persistent effect build and a better batched
search/acceptance rule. Do not claim full-model GPU acceleration yet. The CPU 20 x 10-year
run remains the working result.

## P83.7 full sparse table build (2026-10-30)

The streaming builder completed on the full TSA23 `compiled_ft_econ` model:

- candidate rows: **20,237,499**
- target cells: **200**
- nonzeros: **25,320,796**
- sparse table bytes: **567 MB**
- build seconds: **1,340 s** (~22 min)
- peak CPU RSS: **~29 GB**
- upload to GPU: **568 MB**

So the full table is feasible, but the cold build is too slow for interactive use and the
table is not persisted yet. The 5,000-block prototype still has poor search quality; full
GPU search quality is not measured. Next steps are table save/load (or a persisted CSR
sidecar) and a better batched search/acceptance rule.

### Table persistence

`EffectTable.save` / `EffectTable.load` now persist the CSR tensors and row index as one
torch archive. A round-trip test covers the sparse tensors, blocks, row index, and deltas.
This makes the one-time 22-minute full-model build reusable; the next run can load the
table instead of rebuilding.

## P83.8 full TSA23 population run (2026-10-30)

Using the persisted 567 MB sparse table on the full `compiled_ft_econ` model:

- dataset/candidates: 74.5 s
- table load: 113.9 s
- population option-map construction: **410.1 s**
- 64 genomes, 10 generations: **9.3 s** search
- objective: 21.02M initial -> **9.12M**
- 704 genome evaluations; best at generation 10
- VRAM: 1.14 GB; host RSS: 12.5 GB

The table itself is fine; the full model's **option-map construction** is now the dominant setup
cost. Ten generations are nowhere near the CPU 20x10 result (objective 0), so this is a
negative/partial result, not a full-model win. Persisting the population/option map and
running a longer budget is the next storage/performance problem.

