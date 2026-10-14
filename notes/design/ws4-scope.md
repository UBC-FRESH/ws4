# WS4 Scope

Status: draft
Phase: P0 (Scope and design)
Date: 2026-10-14

## Problem statement

Forest planning decisions are spatial. Which stands to harvest, in what order, and how the resulting
openings relate to one another, to water, to viewsheds, and to the road network, all depend on where
things are. Most estate models answer the "how much" question well but treat the "where" question as a
post-processing step: solve an aspatial problem, then scatter the result across a map.

WS4 is a forest estate model that makes space part of the problem. It is CLI-first and built for
multi-core Linux hosts, so it can run large landscapes, many scenarios, and long horizons without a
desktop environment.

## Users

- **Analysts** who build a model from a landscape inventory and a management recipe, run scenarios, and
  compare outcomes.
- **Planners** who set objectives (wood flow, habitat, patch size, cost) and need a defensible schedule.
- **Researchers** who extend the model with new treatments, growth behaviour, spatial constraints, or
  solvers.
- **Agents** that operate the CLI, inspect datasets, and report results with evidence.

## Goal

Deliver a spatially explicit, reproducible, HPC-ready simulation and planning engine whose inputs and
outputs are inspectable datasets, and whose spatial relationships are enforced in the model.

## In scope (through the first release)

- A fragment-level inventory model with blocks as a runtime aggregate.
- An ingestion and compilation step that turns a **ForestModelXML** recipe and a fragment inventory into
  a versioned, columnar **matrix** dataset, and that ingests legacy datasets directly.
- An annual simulation engine with growth, succession, treatments, and block-level operability.
- A spatial subsystem: block adjacency and topology, patch metrics and patch objectives, and core-area
  handling.
- A road and route subsystem: a network model with access, haul cost, destination eligibility, and
  exclusive (one-of-many) routing.
- An optimization engine: weighted goal programming with a layered, pluggable search stack
  (operators, metaheuristics, a portfolio layer, and tuners) generalized from the lab's FHOPS toolkit,
  with MIP bounds, warm starts, and destroy-repair subproblems.
- Tuning and a meta-meta-heuristic portfolio driven by a telemetry store.
- Multi-core and GPU execution: a NUMA-aware process pool, island metaheuristics, tensorized GPU move
  evaluation, and parallel math-heuristics.
- A Python-first implementation, with measured bottleneck kernels ported to C++ behind a stable Python
  API.
- Accounts and reporting over fragments, blocks, groups, patches, and routes.
- A CLI (`build`, `simulate`, `optimize`, `validate`, `report`) and a small configuration surface.
- Reproducibility: recorded seeds, deterministic simulation, and validated datasets.

## Out of scope (for now)

- A graphical interface or map viewer.
- A carbon accounting module and links to external carbon models.
- Supply-chain and mill-optimization modules beyond route destinations.
- Exact mixed-integer spatial optimization (revisited only if the metaheuristic proves insufficient).
- Writing back vendor-specific runtime artifacts beyond the ForestModelXML recipe and the fragments
  inventory.
- A hosted service or database backend.

## Relationship to WS3

WS3 is an aspatial estate model with an exact optimizer and a post-hoc raster allocator. WS4 keeps the
domain vocabulary that analysts already use (development strata, tracks, treatments, curves, products,
targets) but changes the representation: spatial units are the decision units, the runtime contract is
a compiled dataset, and spatial structure is enforced during simulation and optimization. WS3 remains
the reference for aspatial formulation and for concepts that carry over.

## Success criteria

- A synthetic landscape compiles, simulates, and optimizes end to end from the CLI.
- A schedule produced by the optimizer satisfies its targets within stated tolerances, and the
  simulation that replays it reproduces the same account values.
- Spatial constraints (adjacency, maximum opening size, green-up) are visible in the outputs and can be
  violated only by an explicit override.
- The compiled dataset round-trips through a documented schema and validates against its manifest.
- A full run is reproducible from its configuration and seed.

## Constraints and assumptions

- Python 3.11+ on Linux, with columnar data (Parquet/Arrow) and vectorized kernels.
- The first release targets correctness and clarity over raw speed, but the design must not preclude
  multi-core scaling.
- The compiled dataset is the boundary between ingestion and execution; execution never reads the raw
  source inventory directly.
