# P83.9 fixed round-robin master/worker portfolio

Date: 2026-10-30
Worktree: `feature/p83-meta-portfolio` at `7439cab`
GPU: NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition
PyTorch: 2.14.1+cu130

## Scope

This is the first bounded move in `notes/design/ws4-metaheuristic-portfolio.md`: a fixed
round-robin master/worker portfolio with one elite archive, explicit migration, exact
master verification, and no adaptive credit.  It is not wired into the CLI.

## What was added

- `ws4/opt/meta_portfolio.py`
  - `MetaPortfolio`: fixed worker allocation, one round-robin pass per round, and a
    worker-local evaluator per method.
  - `PortfolioArchive`: a bounded master archive of distinct complete schedules, best
    objective first.
  - `WorkerSpec`: the fixed slot definition for SA, tabu, ILS, GA, and LNS.
  - `Migration`: an explicit record of the archive rank sent to a worker, the seed
    objective, the returned objective, the wall-clock, and the evaluation count.
  - `MethodContribution`: slices, retained returns, improvements, best objective, best
    gain, seconds, and evaluations per method.
  - `default_worker_specs`: the seven-slot AGrp-style mix (two SA, tabu, ILS, GA, LNS, and
    a diverse-restart SA).
- `ws4/opt/gpu_ga.py`
  - `GenomePopulation.reseed`: a persistent GA worker can take a new elite without
    rebuilding its option map or sharing its population.
  - `GenomePopulation.run(..., deadline=...)`: the GPU population can use the same
    wall-clock budget as the CPU and portfolio paths.
- `examples/gpu_effects/portfolio_c5.py`: the bounded equal-budget c5 2,000-block
  comparison.
- `tests/test_meta_portfolio.py` and the two new `tests/test_gpu_ga.py` cases.

## Protocol

The master owns the archive.  A worker receives one complete archive schedule and returns
one complete schedule.  It never receives the master's evaluator, the archive, or another
worker's state.

- Regular workers are seeded from the best recorded elite, the AGrp master-best rule.
- A diverse-restart slot walks the archive from the far end.
- The master re-evaluates every returned schedule with a fresh
  `IncrementalObjective` and raises if the worker's claimed objective differs.
- A return enters the archive only when it is a distinct schedule and the archive is not
  full of better schedules.
- The final incumbent is re-evaluated once more before it is returned.

CPU workers use a candidate-preserving move registry: toggle, shift, and LNS.  Swap is
excluded from the portfolio because it can move a chain to a block where the effect table
has no row; the candidate-index GA genome cannot represent that schedule.  A CPU elite is
therefore always a schedule the GA option map can represent.

## Exactness

The focused suite is:

```text
pytest -q tests/test_meta_portfolio.py tests/test_gpu_ga.py tests/test_gpu_search.py \
    tests/test_archive.py -o addopts=''
41 passed
```

The portfolio tests cover the archive capacity and de-duplication rules, fixed
round-robin migration records, deterministic re-runs, the diverse-restart seed, the
time-limit stop, candidate/table validation, the GA worker, the GPU LNS worker, and the
master objective oracle (a worker claim that disagrees with the exact evaluator raises).

## c5 2,000-block benchmark

Inputs:

- Compiled dataset: `c5_compiled` (7,257 blocks).
- Targets: `targets_balanced_stock79.yaml` (401 target cells).
- Seed: `seed_stage1.csv`.
- Slice: the first 2,000 seed blocks.
- Effect table: 456,278 rows, 1,578,701 nonzeros, 28.9 MB, built in 9.0-9.3 s.  The table
  build and upload are shared and excluded from the search budget.
- Seed objective: 2,414,274,207.31.
- Search budget: 15 s for the portfolio and 15 s for the single method.
- Portfolio: seven fixed workers; SA 400 iterations, tabu 10, ILS 20, GA 200 generations,
  CPU LNS 400; rounds repeated until the deadline.
- Single method: P83.8 GPU `GenomePopulation`, population 224, one island, seeded from the
  same initial schedule, run until the same deadline (construction included).

| Seed | Portfolio objective | Portfolio s | Single GA objective | Single GA s | GA generations | Portfolio vs GA |
|---:|---:|---:|---:|---:|---:|---:|
| 7 | 35,913,440.27 | 15.046 | **35,794,501.99** | 15.005 | 2,079 | +0.33% |
| 8 | 36,153,536.44 | 15.035 | **35,680,047.18** | 15.010 | 2,599 | +1.33% |
| 9 | 36,068,040.77 | 15.049 | **35,852,901.04** | 15.007 | 2,805 | +0.60% |
| mean | 36,045,005.82 | 15.043 | **35,775,816.74** | 15.007 | 2,494 | +0.75% |

A separate equal-budget CPU check on seed 7 gave:

| Single method | Budget | Exact objective |
|---|---:|---:|
| CPU SA (`solve_sa_delta`, stock registry) | 15.0 s | 36,090,529.99 |
| CPU LNS (`solve_sa_delta`, LNS only) | 15.0 s | 46,475,324.78 |
| GPU GA | 15.0 s | **35,794,501.99** |

The GPU GA is the best single method at this budget in these runs.

## Method contributions

| Seed | Method | Slices | Retained | Improved | Best returned | Seconds |
|---:|---|---:|---:|---:|---:|---:|
| 7 | GA | 2 | 2 | 2 | **35,913,440.27** | 10.77 |
| 7 | SA | 6 | 6 | 6 | 36,031,970.59 | 0.79 |
| 7 | ILS | 2 | 1 | 1 | 36,031,970.59 | 0.46 |
| 7 | tabu | 2 | 1 | 1 | 36,031,970.59 | 0.54 |
| 7 | LNS | 2 | 0 | 0 | 35,913,440.27 | 1.82 |
| 8 | SA | 11 | 11 | 11 | **36,153,536.44** | 1.11 |
| 8 | GA | 3 | 3 | 3 | 36,188,087.58 | 9.19 |
| 8 | ILS | 3 | 2 | 2 | 36,221,129.71 | 0.79 |
| 8 | tabu | 3 | 2 | 2 | 36,221,129.71 | 0.77 |
| 8 | LNS | 3 | 0 | 0 | 36,188,087.58 | 2.24 |
| 9 | GA | 4 | 4 | 4 | **36,068,040.77** | 9.02 |
| 9 | SA | 11 | 11 | 11 | 36,084,426.62 | 1.75 |
| 9 | ILS | 4 | 3 | 3 | 36,084,426.62 | 0.81 |
| 9 | tabu | 4 | 2 | 2 | 36,084,426.62 | 0.90 |
| 9 | LNS | 3 | 0 | 0 | 36,121,986.07 | 1.65 |

The GA produced the portfolio incumbent on seeds 7 and 9, and the SA restart produced it on
seed 8.  Tabu and ILS improved weak early elites but never produced the final incumbent.

## Negative result

At equal 15-second search budgets the fixed portfolio is **0.33-1.33% worse** than the best
single method, the GPU GA (mean +0.75%).  It is better than single CPU SA (36.09M) and CPU
LNS (46.48M) on seed 7, so the negative result is specifically against the strongest single
method, not against every single method.  The reason is visible in the counters:

- the first GA slice pays the population option-map construction (roughly 6 s for this
  table), and the persistent `reseed` path avoids paying it again;
- the fixed mix gives the GA only 2-4 slices (400-800 generations) in 15 s, while the
  single GA runs 2,079-2,805 generations;
- LNS never improved a seed and never entered the archive on any of the three seeds;
- tabu and ILS only repaired the early, weak elites.

This is the expected failure mode for a fixed unfocused mix: a strong method loses most of
its budget to the other slots.  Do not claim portfolio superiority from this run.  The next
step, adaptive credit, should give the GA more slices once it demonstrates the gain, then
re-run the same equal-budget benchmark.

## Limitations

- This is a 2,000-block c5 slice, not the full model or TSA23.
- Time-limited runs are not reproducible from their seeds alone, because the deadline
  decides how many rounds finish.
- The GA and GPU LNS workers keep their existing one-priority, no-patch, no-route,
  no-spatial exactness contracts.
- The portfolio uses the exact incremental objective for verification, but the CPU tabu
  and ILS workers still evaluate whole schedules per sampled move.
- No adaptive credit, no CLI wiring, and no full method-mix benchmark yet.
