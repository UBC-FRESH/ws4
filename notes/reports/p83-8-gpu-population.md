# P83.8 GPU-native population search

Date: 2026-10-30
Worktree: `feature/p83-gpu-population` at `7a1aefc`
GPU: NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition
PyTorch: 2.14.1+cu130

## Scope

This is the bounded population prototype from
`notes/design/ws4-gpu-population-search.md`.  It adds a candidate-index genome, batched
fitness through the sparse `EffectTable`, elitism, tournament selection, uniform crossover,
mutation, and optional island/AGrp elite exchange.  The CPU simulated annealer remains the
reference and the fallback.  No target semantics, optimizer loop, or CLI wiring changed.

## What was added

- `ws4/opt/gpu_ga.py`: `GenomePopulation` with a seed genome, random genomes, seeded
  mutants, uniform crossover, tournament selection, per-island elitism, ring migration, and
  the adapted MQT AGrp elite exchange, plus `PopulationResult` and state save/load.
- `ws4/opt/gpu_search.py`: an absolute `_ObjectivePricer.scores` path for population
  fitness, exact handling of a non-positive even-flow reference balance, and an explicit
  rejection of `ndy` flow.
- `tests/test_gpu_ga.py`: exactness (level and even-flow targets), operator validity,
  elitism, tournament selection, island/AGrp migration, invalid inputs, and save/load.
- `examples/gpu_effects/search_ga.py`: the c5/TSA23 benchmark against stock CPU SA/LNS and
  the batched GPU LNS prototype.

## Representation and exactness

A genome is one candidate index per block.  A seed chain that is not a candidate is
appended to that block's options and given an extra effect row; there is no repair pass.
Fitness is the base totals plus the segmented sum of the genome's effect rows, then the
same device pricer used by the batched LNS prototype.

The prototype prices one priority tier, no patch accounts, no route accounts, and no
spatial rules.  It raises `NotImplementedError` on mixed priorities, patch/route/spatial
targets, or `ndy` flow.  The c5 balanced targets and the TSA23 20 x 10-year even-flow target
are inside that contract.

Exactness checks:

| Check | Genomes / moves | Tolerance | Result |
|---|---:|---|---|
| Unit tests, level targets | 16 genomes per population | rel 1e-9, abs 1e-6 | pass |
| Unit tests, even-flow target | 16 genomes per population | rel 1e-9, abs 1e-6 | pass |
| c5 benchmark, first generation | 8 genomes | rel 1e-9, abs 1e-6 | pass |
| TSA23 5k, first generation | 4 genomes | rel 1e-9, abs 1e-6 | pass |
| Final schedules | one per run | fresh `IncrementalObjective` | pass |

The final schedule of every benchmark run was re-evaluated from scratch; the reported
objective is that fresh value, not the device score.

## Inputs

- c5: `c5_compiled`, `targets_balanced_stock79.yaml`, `seed_stage1.csv`, first 2,000 seed
  blocks.
- TSA23 5k: `compiled_ft_econ`, `evenflow_ft_econ_20x10.yaml`,
  `seed_evenflow_ft_econ_20x10.csv`, first 5,000 seed blocks.
- The full 20.2M-row TSA23 table was **not** rebuilt.

## Effect tables

| Quantity | c5 2k | TSA23 5k |
|---|---:|---:|
| Blocks | 2,000 | 5,000 |
| Rows | 456,278 | 1,590,695 |
| Nonzeros | 1,578,701 | 1,999,367 |
| Target cells | 401 | 200 |
| Sparse table | 28.9 MB | 44.7 MB |
| CPU build | 9.64 s | 59.10 s |
| Upload | 0.12 s | 0.13 s |

## c5 2k population search

Population 256, 500 generations = 128,256 genome evaluations.  CPU baseline is
`solve_sa_delta` with the stock `LnsOperator`, 30,000 iterations.  GPU LNS is the batched
prototype with 256 proposals per round and 500 rounds (128,000 proposals).  Search times
exclude the one-time table build and upload.

| Seed | CPU objective | CPU s | GPU LNS objective | LNS s | GA objective | GA s | GA speedup | GA with build |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | 42,329,754 | 41.22 | 37,739,927 | 17.61 | **36,173,249** | 1.58 | **26.0x** | **3.63x** |
| 8 | 45,149,589 | 28.19 | 38,832,063 | 17.74 | **36,092,563** | 1.36 | **20.8x** | **2.54x** |
| 9 | 40,935,666 | 28.03 | 37,302,113 | 17.13 | **36,172,236** | 1.30 | **21.6x** | **2.53x** |

- The population objective is **4.1-6.7M better** than the stock CPU baseline and
  **1.1-2.7M better** than the batched GPU LNS on every seed.
- Search-only speedup is **20.8-26.0x**; a single cold run is still **2.5-3.6x** including
  the 9.6 s build and 0.12 s upload.
- The first CPU seed is slower than the next two because the optimizer contribution caches
  are cold.  The later CPU runs are the fairer steady-state reference.
- Peak VRAM: **220.9 MB allocated / 266.3 MB reserved**.

## Island and AGrp exchange

The added context describes the MQT 8000 AGrp hierarchy: a master owns the population,
workers run GA seeded with the master best, elites return and replace the worst, and state
was exchanged through a job server.  The GPU adaptation uses the population tensor as the
master and contiguous worker islands as the workers.  Selection, crossover, mutation, and
elite placement stay on the device; the job server is unnecessary because the effect table
and population already share device memory.  `exchange="agrp"` returns each worker's best
migrants, keeps the global elite set, and re-seeds every worker's worst with it.

c5 2k, population 224, 500 generations, seven workers, exchange every 10 generations,
two migrants:

| Configuration | Seed 7 objective | Seed 8 objective | Seed 9 objective | GA s |
|---|---:|---:|---:|---:|
| One island | **36,028,989** | **35,968,830** | **36,119,657** | 1.26-1.92 |
| Seven workers, ring | 36,240,279 | 36,527,555 | 36,336,559 | 2.84-3.19 |
| Seven workers, AGrp | 36,082,899 | 36,215,637 | 36,393,359 | 2.98-3.59 |
| Seven workers, AGrp every 25 | 36,010,395 | 36,423,991 | 36,484,002 | 2.89-3.77 |

This is a **negative result**: AGrp is better than ring on two of three seeds but neither
island variant beats the one-island run, and both are about twice as slow because the
per-island elite and tournament steps are separate Python-level slices.  Diversity is not
the c5 2k bottleneck; the one-island population is already small enough to breed cheaply
and converge.  A production island path would need vectorized per-island top-k and a
reason to trade throughput for diversity.

## TSA23 5k subset

Population 256, 500 generations = 128,256 evaluations.  CPU baseline is stock SA with 5,000
iterations.  GPU LNS is the bounded 64-proposal, 100-round prototype from P83.7.

| Seed | CPU objective | CPU s | LNS objective | LNS s | GA objective | GA s | GA speedup | GA with build |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | 76,540,099 | 10.27 | 315,398,751 | 2.59 | **75,413,714** | 4.27 | 2.40x | 0.16x |
| 8 | 76,507,080 | 2.19 | 289,744,692 | 2.17 | **75,337,674** | 1.23 | 1.79x | 0.036x |

- The population is **1.0-1.1M better** than CPU SA, a roughly 1.5% quality gain.
- The batched best-of-batch LNS is still poor here (289-315M), matching the P83.7 finding
  that one accepted proposal per round is not enough.
- The cold table build dominates: including its 59.1 s, a single run is **0.04-0.16x** the
  CPU wall time.  With a persisted table, the warm GA is 1.8-2.4x faster at slightly better
  objective, but that is below the 2x target on one of two seeds and is not a decisive win.
  The CPU 20 x 10-year run remains the working TSA23 result.
- Peak VRAM: **230.7 MB allocated / 295.7 MB reserved**.

## Interpretation

- On c5 2k the population search is exact, fast, and clearly better than the stock CPU
  baseline: 20-26x search-only and 2.5-3.6x including the cold build.
- On TSA23 5k the population gives a small quality gain and a 1.8-2.4x warm speedup, but
  the 59 s build makes a cold run slower than CPU.  This is a limited positive result, not
  a full-model claim.
- Islands and the AGrp master-best exchange did not improve c5 quality at this budget and
  cost about 2x wall time.  The no-island population is the recommended prototype.
- The prototype supports one priority tier and no patch, route, or spatial pricing.  It
  raises on anything else; the CPU SA remains the fallback.

## Decision

The c5 population search is exact and measurably useful, so it is committed on
`feature/p83-gpu-population` for cherry-pick.  The TSA23 5k result and the island/AGrp
negative result are recorded rather than promoted.  Do not replace the CPU SA and do not
claim full-model GPU acceleration.  The next useful steps are a persisted-table load path
for TSA23 and vectorized island top-k if diversity is needed.
