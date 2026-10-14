# WS4 Optimization and Execution Architecture

Status: draft
Phase: P0 (Scope and design)
Date: 2026-10-14
Related: `notes/design/ws4-architecture.md` (section 8 and 14), `notes/adr/0004`, `notes/adr/0007` to `notes/adr/0010`

## 1. Motivation

Forest planning objectives are non-linear, spatial, and conflicting, so an exact mixed-integer
formulation of a full landscape over a long horizon is usually intractable. The lab already has a
proven optimization toolkit in the FHOPS project: three metaheuristics (simulated annealing, tabu
search, and iterated local search), three hyperparameter tuners (random, grid, and Bayesian), a shared
neighbourhood-operator registry, and a telemetry store. This note generalizes that toolkit into a
reusable solver core, adds a meta-meta-heuristic layer and parallel math-heuristics, and sets the
execution substrate for a multi-core CPU host with a large GPU.

## 2. The layered stack

```text
  L4  tuning / meta-meta-heuristic   random | grid | Bayesian | ML-boosted portfolio
        ^ telemetry
  L3  portfolio and adaptation       island model | elite sharing | operator-weight adaptation
        ^ telemetry
  L2  metaheuristics                 SA | Tabu | ILS | multistart | ALNS
        ^ operator stats
  L1  neighbourhood operators        toggle | shift | swap | block-insertion | patch | route
        ^ proposals
  L0  problem and objective          weighted goal programming over accounts and targets
  ---------------------------------------------------------------------------------------------
  L5  math-heuristic layer           MIP (bounds, warm starts, destroy-repair subproblems)
```

- **L0 — problem and objective.** Weighted goal programming: each target contributes a penalty for
  shortfall below its minimum and excess above its maximum, per period, scaled by weights and an
  optional discount rate, with linear or quadratic scaling (`notes/adr/0004`).
- **L1 — operators.** Domain neighbourhoods behind one `Operator` interface with a name and a weight.
  WS4 adds spatial and road operators to the harvest-scheduling operators: patch-coherent moves,
  adjacency/green-up moves, and route/access moves.
- **L2 — metaheuristics.** SA, Tabu, ILS, multistart, and ALNS share an execution context (problem,
  current schedule, RNG, feasibility sanitizer, distance/window lookups) and the same operator
  registry, so a solver swap does not change the move set.
- **L3 — portfolio and adaptation.** A portfolio layer runs one or more metaheuristics (as islands),
  shares elite solutions, and adapts operator weights online from acceptance statistics (ALNS-style).
  This is the "meta-meta-heuristic": it chooses and steers the metaheuristics rather than being one.
- **L4 — tuning.** Random, grid, and Bayesian (Optuna TPE) tuners over the tuning surface (operator
  weights, batch size, temperature, tenure, perturbation strength, restarts). An ML-boosted layer adds
  surrogate models and cross-scenario meta-learning: predict good configurations and stopping budgets
  from scenario descriptors and telemetry.
- **L5 — math-heuristic layer.** A MIP solver (HiGHS, optionally Gurobi) provides lower/upper bounds
  for gap tracking, warm starts when a heuristic stalls, and time-boxed destroy-repair subproblems
  inside large-neighbourhood search. The heuristic keeps spatial structure; the MIP solves the linear
  subproblem.

## 3. Generalization and reuse

The L1–L4 layers and the telemetry store form a solver core that is parameterized by a **problem
adapter** (objective, feasibility, move application, and scenario descriptors). WS4, WS3, and FHOPS
each supply an adapter. The core is the same code in all three; the adapters differ. This avoids
maintaining three copies of the metaheuristics, tuners, and telemetry.

Recommended default: host the solver core as its own internal package (for example, `fresh-opt`) that
WS4 depends on. Reason: the toolkit predates WS4 and is shared; a separate package keeps the
dependency direction clean.

## 4. Telemetry and the meta-meta-heuristic

Every run records a structured record: configuration, seeds, per-step objective trajectory, operator
proposal/acceptance statistics, acceptance rate, timing, and scenario descriptors (fragment/block/
machine counts, horizon, spatial density). The meta-meta-heuristic consumes this store to:

- adapt operator weights online within a run;
- select a portfolio of metaheuristics across runs and scenarios;
- recommend iteration budgets and stopping criteria from a fitted convergence model (gap versus
  iterations versus scenario features);
- transfer tuned presets across scenarios with similar descriptors.

## 5. Execution substrate

The host is a two-socket node (2 × Intel Xeon Gold 6254, 18 cores each, 72 logical CPUs, two NUMA
nodes, 754 GB RAM) with an NVIDIA RTX PRO 6000 Blackwell (96 GB). The substrate has four lanes:

1. **CPU process parallelism.** A process pool over the logical CPUs, NUMA-aware, with per-worker
   seeds so a parallel sweep reproduces a serial one. Batched neighbour evaluation uses a thread pool
   inside a worker.
2. **Island metaheuristics.** Multiple searchers run concurrently and exchange elites periodically
   (asynchronous, so a slow island does not stall the rest).
3. **GPU move evaluation.** Tensorize the hot operators: represent the schedule as tensors and
   evaluate many candidate moves at once, returning the best (the tensor-based local-search pattern).
   Start with PyTorch (the driver is present; no CUDA toolkit build is required) and fall back to the
   CPU when the GPU is not the bottleneck.
4. **Parallel math-heuristics.** Solve several MIP subproblems concurrently, and run a MIP lane beside
   the heuristic lane for bounds and warm starts.

## 6. Language strategy

- **Python first.** Prototype the core functions in Python and keep a Python reference implementation.
- **Profile, then port.** Move only the measured bottleneck kernels to C++ behind a stable Python API
  (pybind11 or nanobind), with a NumPy buffer interface and no Python object churn in the hot loop.
- **Language-agnostic interfaces.** Keep the operator and metaheuristic interfaces free of Python-only
  types so a C++ kernel is a drop-in replacement.
- **Candidate kernels.** Neighbour scoring, adjacency/patch checks, route cost, and the annual
  simulation loop.

## 7. What this buys, and its limits

- The meta-meta-heuristic improves robustness across scenario families without hand-tuning each one.
- Parallel math-heuristics give gap-tracking and warm starts that a pure heuristic cannot.
- GPU move evaluation helps when neighbourhood evaluation dominates; it does not help a search that is
  latency-bound by sequential decisions.
- C++ kernels help the annual loop and neighbour scoring; they add a build and ABI surface that must be
  justified by profiling.

## 8. Open questions

1. **Solver-core boundary.** A separate internal package versus a module inside WS4. Default: separate
   package (section 3).
2. **GPU first target.** Which operator to tensorize first. Default: the swap/shift family on the
   harvest schedule, because it dominates proposal volume.
3. **Math-heuristic cadence.** How often to call the MIP lane. Default: on stall, with a time box.
4. **ML scope.** Surrogate tuning first; meta-learning across scenarios only after the telemetry store
   has enough runs.

## 9. Background

- Tensor-based GPU acceleration of local-search move evaluation (attribute-based solution tensors).
- GPU adaptive large neighbourhood search and GPU large neighbourhood search for constraint programming.
- Island-model GPU metaheuristics (PSO/GA/SA) and hybrid asynchronous metaheuristics.
- ML-guided neighbourhood selection (for example, latent-representation-guided parallel ALNS).
- The lab's FHOPS toolkit: SA, Tabu, ILS; random, grid, and Bayesian tuners; telemetry and reporting.
