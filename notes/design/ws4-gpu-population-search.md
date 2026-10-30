# GPU population search plan

Phase identifier: P83
Task identifier: P83.8
Parent phase issue: #579
Branch: `feature/p83-gpu-population`
Status: active
Date: 2026-10-30

## Goal

Add a GPU-native population search for WS4 and measure it against the existing CPU SA/LNS
and GPU parallel-chain prototype. The purpose is throughput and diversity on large models,
not a new name for the same local search.

## Why population search

Every current WS4 variant except the parallel-chain prototype is one trajectory:
propose one move, evaluate it, accept/reject, update state. That leaves the GPU idle between
moves. A population evaluates many independent genomes per generation, so candidate
evaluation, selection, crossover, and mutation can be batched on the device.

The current GPU parallel-chain prototype already gives 154k moves/s on a 2k c5 slice, but
it has no crossover or elite recombination. P83.8 adds the population structure.

## Representation

### Genome

A genome is one candidate-chain index per block:

```text
genome[block] = candidate index
```

The candidate-list order is stable for a fixed dataset/config. The seed schedule maps to a
seed genome; blocks whose seed chain is not a candidate get an extra effect row and are
held fixed or given a nearest candidate during initialization.

This is a **candidate-index genome**, not a random-key genome. It avoids the continuous
decoder for a categorical treatment choice. BRKGA/random-key can be a later comparison.

### Fitness

Fitness is the exact WS4 target objective:

- level targets from the selected period cells,
- even-flow/NDY targets from period balances,
- feature stock cells,
- one priority tier for this prototype.

The fitness comes from the effect table: one genome's cell totals are the segmented sum of
its B effect rows. The population score is `[P, cells]`, then the existing GPU penalty
pricer.

## GPU layout

```text
effect table: CSR [rows, cells]          567 MB full TSA23
genome rows:  [P, B] int32/int64         P x 66k ints
cell totals:  [P, cells] float64         P x 200
```

For the full TSA23 model:

| Population | Genome ints | Approx int64 memory |
|---:|---:|---:|
| 256 | 16.9M | 135 MB |
| 512 | 33.8M | 270 MB |
| 1,024 | 67.7M | 542 MB |

The 567 MB table fits easily in 96 GB VRAM. Fitness evaluation is the expensive part:
`P x B` effect rows per generation, so generation size must be chosen from measured row
throughput, not from the number of candidate names.

## Operators

### Initialization

- seed genome from the accepted schedule,
- 10–20% random genomes,
- the rest seeded with light mutations of the seed genome.

### Selection

- elitism: keep the top 10%,
- tournament selection for parents,
- optional island-local elitism.

### Crossover

- uniform crossover over block positions,
- per-block candidate indices remain valid by construction,
- no repair pass for candidate validity.

### Mutation

- mutate a small fraction of blocks per genome,
- include a “stay with current chain” mutation to avoid churn,
- optionally use LNS as a memetic local improvement after crossover.

### Islands

- P subpopulations on separate streams,
- migrate the best few genomes every N generations,
- asynchronous copy/migration, no device-wide barriers,
- record which island produced the incumbent.

## Milestones

### P83.8.1 — c5 2k slice

- P = 256, 500 generations, seed genome plus random/mutation initialization.
- Compare against CPU SA/LNS and the GPU parallel-chain prototype.
- Acceptance: exact fitness against `IncrementalObjective`; at least 2x the CPU wall time
  at equal or better objective, or a measured negative result.

### P83.8.2 — TSA23 5k subset

- Use the 20 x 10-year even-flow target.
- Table build is already measured at ~64 s; run a bounded generation budget.
- Record quality and wall time; do not compare a short GPU run to a full CPU 100k run.

### P83.8.3 — TSA23 full model

- Load the persisted full sparse table.
- P = 256–512, chunked genome-row evaluation.
- Record VRAM, generation time, objective, and whether the result is competitive with the
  CPU 20 x 10-year run (386 s, objective 0).

## Acceptance and oracles

- Compare population fitness against a fresh `IncrementalObjective` on selected genomes.
- Compare the best genome’s schedule against the CPU objective.
- Report CPU wall, GPU wall, table build/load, VRAM, generations, evaluations, and quality.
- A negative result is acceptable and must name the bottleneck.
- Dashboard green before closing.

## Risks

- A candidate-index genome cannot represent a seed chain absent from the candidate list;
  handle those as extra fixed rows or nearest candidates and record which.
- Full TSA23 fitness is `P x 66k` effect rows per generation; chunk it.
- Population methods may need more evaluations than LNS; GPU throughput may not translate
  to better quality.
- The current batched pricer supports one priority tier and no patch/route/spatial rules.
- Table rebuild is ~22 minutes; persistence is required for iterative work.

## First implementation

Create `ws4/opt/gpu_ga.py` with:

- `GenomePopulation` (seed, random, mutation, uniform crossover),
- a batched `evaluate` over an `EffectTable`,
- tournament/elitism and optional island migration,
- an example benchmark on the c5 2k slice,
- exactness tests against `IncrementalObjective`.

Do not wire it into the CLI until the prototype is exact and measured.

## AGrp-derived master/worker structure

The MQT 8000 archive's working hierarchical prototype is the parallel GA (`AGrp`), not a
four-method hybrid. Its structure is worth reusing:

- the master owns the main population and selection policy;
- seven subordinate workers run GA searches seeded with the master's best solution;
- a finished worker returns an elite;
- the master replaces the worst population member and launches the next worker;
- the channel is a job server, not shared RAM or a shared file.

For WS4, the GPU analogue is:

- master owns the population, elite archive, and migration policy;
- each GPU island evaluates a batch of genomes or independent chains;
- elites migrate to the master at generation boundaries;
- the next batch is seeded from the current elite set;
- no device-wide barrier and no Python per-solution loop.

The important measured result is quality: AGrp reduced mean relative error from 0.191% to
0.053% and found the optimum 45% vs 15% of the time. Wall-clock/per-iteration claims from
the old course archive are not cleanly tabulated, so do not reuse them; measure WS4
directly.

Use this structure in P83.8, but keep the GPU implementation and exact WS4 target
semantics separate from the old knapsack code.
