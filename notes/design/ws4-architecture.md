# WS4 Architecture

Status: draft
Phase: P0 (Scope and design)
Date: 2026-10-14
Related: `notes/design/ws4-scope.md`, `notes/adr/0001` to `notes/adr/0006`

## 1. Context and goals

WS4 is a spatially explicit forest estate model. It is CLI-first and HPC-ready, and it is designed so
that spatial relationships (adjacency, patch structure, road access) are part of the model rather than
a post-processing step.

The design has three goals:

1. **Spatial explicitness.** The decision unit is a spatial unit, and the constraints that matter
   operationally (block contiguity, maximum opening size, green-up, access) are enforced during
   simulation and optimization.
2. **A single, inspectable contract.** Ingestion compiles a management recipe and a fragment inventory
   into one versioned dataset. Everything downstream reads only that dataset.
3. **Reproducibility and scale.** Runs are reproducible from configuration and seed, and the design
   scales from a laptop to a multi-core host.

## 2. Design principles

- **Fragments compile, blocks aggregate.** Compilation happens at the fragment level. A block is a
  runtime view over its fragments; its product and feature attributes are summed on the fly.
- **Columnar and vectorized.** The compiled dataset is columnar (Parquet/Arrow), and hot loops are
  vectorized over fragments.
- **Explicit boundaries.** The compiled dataset is the boundary between ingestion and execution. The
  simulator and the optimizer never read the raw inventory.
- **Spatial constraints are data.** Adjacency, patch classes, and route access are represented as
  tables, not hard-coded rules.
- **Deterministic where it matters.** Simulation is deterministic given a schedule. The optimizer is
  stochastic but records its seed and checkpoints its state.
- **Contracts before code.** Interfaces and schemas are fixed in `docs/` before implementation.

## 3. System overview

```text
  management recipe (XML)        fragment inventory (vector)
              \                        /
               \                      /
                v                    v
            +---------------------------+
            |      ingest / compile     |   (P1, P2)
            +---------------------------+
                          |
                          v
            +---------------------------+     +---------------------+
            |   compiled matrix dataset |<--->|  topology, roads,   |
            |   (columnar + manifest)   |     |  targets, scenario  |
            +---------------------------+     +---------------------+
                 |                |
                 v                v
        +----------------+  +----------------+
        |   simulator    |  |   optimizer    |
        | (annual steps) |  | (goal search)  |
        +----------------+  +----------------+
                 \                /
                  v              v
            +---------------------------+
            |  accounts, reports, maps  |
            +---------------------------+
```

The two execution paths share the compiled dataset and the account definitions. The simulator replays a
schedule; the optimizer searches for one.

## 4. Data model

The canonical model types live in `ws4/model/types.py`. The core types are:

- **Fragment** — the smallest spatial decision unit. Carries an id, its block id, area, age, a track
  id, and an attribute map (species, slope, and other inventory fields).
- **Block** — an operational aggregate of fragments. It has no static product or feature attributes;
  those are computed by summing its fragments.
- **Track** — a succession pathway. A track names a family of growth and yield behaviour and the
  treatments available along it. A treatment can move a fragment to a new track.
- **Stratum** — one development stratum that a track resolves into over time, expressed as an offset
  age with its theme values. A track expands into a sequence of strata.
- **Treatment** — an operation. It carries eligibility and operability predicates (fragment-level), an
  optional new track, an offset adjustment, and a retention setting.
- **Curve** — a growth or yield curve as points `(x, y)` with linear interpolation.
- **Feature** — a per-track attribute curve (for example, area by type, or a structural indicator).
- **Product** — a merchantable output tied to a curve, produced by a treatment, with destination
  eligibility.
- **Account** — a named aggregation of features or products, grouped and optionally summarized.
- **Group** — a named set of blocks used for reporting and for grouped constraints.
- **Target** — a goal-programming objective on an account: minimum, maximum, weights, discount rate,
  and linear or quadratic scaling, per period.
- **Destination** — a mill or facility.
- **Route** — the road network used to reach a destination, with cost and flow.
- **Topology** — an adjacency relation between blocks, used for patch and edge metrics.

Theme values on strata and fragment attributes are the keys that operability and eligibility
predicates are evaluated against.

## 5. The compiled matrix dataset

The compiled dataset is the runtime contract. It is a directory of columnar tables plus a manifest:

| Table | Key columns | Purpose |
| --- | --- | --- |
| `fragments` | `fragment_id`, `block_id`, `area_ha`, `age`, `track_id`, `attrs` | the decision units |
| `blocks` | `block_id`, `type`, `track_id`, `offset`, `area_ha` | the runtime aggregate view |
| `tracks` | `track_id`, `name`, `strata_expr` | succession pathways |
| `strata` | `track_id`, `offset`, `next_age`, `cycle`, theme columns | development strata over offset age |
| `treatments` | `track_id`, `begin`, `end`, `treatment`, `new_track`, `adjust`, `offset`, `retain`, `curve` | available operations |
| `curves` | `curve_id`, `x`, `y` | growth and yield curves |
| `features` | `track_id`, `label`, `curve_id` | per-track feature curves |
| `products` | `track_id`, `treatment`, `label`, `future`, `adjust`, `curve_id` | product definitions |
| `accounts` | `group`, `attribute`, `account`, `sum` | account definitions |
| `groups` | `block_id`, `group` | block grouping |
| `messages` | `severity`, `message` | compile diagnostics |

The manifest records the schema version, the source file identities and hashes, the compile options,
and the table list. A `validate` command checks a dataset against its manifest and against schema
invariants (monotonic ages, non-negative areas, curve domain coverage).

See `notes/adr/0002` for why the dataset is columnar and versioned.

## 6. Compilation

The compile step (`ws4 build`) turns two inputs into the matrix dataset:

- a **management recipe** in XML, describing tracks, treatments, curves, features, products, and
  destinations; and
- a **fragment inventory** as a vector dataset (polygons with attributes).

The algorithm:

1. Parse the recipe into logical definitions.
2. Read the fragment inventory and resolve each fragment's block, area, age, track, and attributes.
3. Resolve, per fragment, the operable and eligible treatments, and expand each track into strata over
   offset age.
4. Resolve feature and product curves per track and treatment.
5. Write the columnar tables and the manifest, and record any diagnostics as messages.

The recipe format is the established **ForestModelXML**, not a new format, and the compiler is a matrix
builder (see `notes/design/ws4-matrix-builder-and-interop.md` and `notes/adr/0011`). WS4 also ingests
legacy datasets directly: an existing matrix directory, a blocks shapefile, a topology table, and a road
model can be read without a recompile.

Compilation is fragment-level by decision (see `notes/adr/0001`). The block shapefile and any launch
control file are **not** compile inputs; blocks are a runtime view, and the launch file only starts a
run.

The compiler is one of two construction paths. WS4 also exposes a programmatic model API that builds or
patches the model in memory for unusual cases and for runtime updates after ingestion, mirroring the WS3
precedent (see `notes/adr/0012`).

## 7. Simulation engine

The simulator (`ws4/sim/engine.py`) steps one year at a time over fragments and aggregates to blocks on
the fly.

Order per year:

1. **Growth** — advance each fragment along its track by offset age, reading feature and product curves.
2. **Succession** — apply breakup and renewal rules; switch tracks and reset offset where the track
   requires it.
3. **Treatments** — apply scheduled operations. A block's operability is the intersection of its
   fragments' operability; if any fragment is inoperable, the block's operation set narrows or empties.
4. **Products and routes** — compute yields and route them to eligible destinations.
5. **Spatial metrics** — compute patch metrics over blocks from aggregated state.
6. **Accounts** — update summary, ratio, patch, and route accounts.

The engine reads the compiled dataset and a schedule (`block_id`, `treatment`, `period`), and writes a
run directory with per-period account values and, optionally, per-fragment state.

See `notes/adr/0005` for the annual-step decision.

## 8. Optimization engine

The optimizer (`ws4/opt/engine.py`) searches for a schedule that satisfies a set of targets. It uses
**weighted goal programming**: each target contributes a penalty for shortfall below its minimum and
excess above its maximum, scaled by per-period weights and an optional discount rate, with linear or
quadratic scaling. The objective is the total weighted penalty.

The search is a parallel metaheuristic:

- **Multi-start** from randomized or seeded schedules.
- **Neighbourhoods**: toggle a treatment, shift a treatment in time, swap two treatments, and
  patch-coherent moves that act on adjacent blocks.
- **Acceptance**: threshold acceptance or annealing.
- **Parallel evaluation** of candidate moves across threads or processes.
- **Convergence**: stop when the objective improves by less than a tolerance over a window of
  iterations, or when a time limit is reached.
- **Checkpoints**: periodically persist the incumbent so a long run can resume.

The optimizer is the top of a layered stack: a weighted-goal objective, a neighbourhood-operator
registry, the metaheuristics, a portfolio/adaptation layer, and a tuning layer, over a shared telemetry
store. The lab's FHOPS toolkit (simulated annealing, tabu search, iterated local search; random, grid,
and Bayesian tuners) is generalized into a solver core that WS4, WS3, and FHOPS share through a problem
adapter. A math-heuristic layer adds MIP bounds, warm starts, and destroy-repair subproblems. The
design is in `notes/design/ws4-optimization-stack.md`.

See `notes/adr/0004` for the choice of a metaheuristic over exact mixed-integer programming, and
`notes/adr/0007` to `notes/adr/0010` for the stack, the language strategy, the parallel/GPU execution
model, and telemetry-driven tuning.

## 9. Spatial subsystem

The spatial subsystem (`ws4/patch/`) provides:

- **Adjacency topology.** A block-to-block adjacency relation, loaded from a topology table
  (`src_block`, `dst_block`, `distance_m`). It supports neighbours, connected components, and patch
  membership.
- **Patch metrics.** Given a block selection (for example, recently treated blocks) and a topology, the
  subsystem groups adjacent selected blocks into patches and computes size classes, counts, and
  perimeter-to-area ratios.
- **Patch objectives.** Targets on patch size classes (minimum, maximum, distribution) participate in
  the objective function like any other account.
- **Core and edge handling.** Core-area rules and edge-contrast specifications between adjacent
  treatments.

Unit handling matters here: map units (metres, square metres) differ from reporting units (kilometres,
hectares). The design carries an explicit conversion factor set so perimeter-to-area ratios are
computed correctly.

## 10. Road and route subsystem

The road subsystem (`ws4/roads/`) models access and haulage:

- **Network model** — vertices, segments, destinations, and linkages loaded from tables.
- **Access** — whether a block can be reached, and the route length to each destination.
- **Haul cost** — cost per unit of product along a route, by destination.
- **Destination eligibility** — which products may flow to which destinations.
- **Exclusive routing** — a one-of-many relationship: a block's volume is assigned to exactly one of
  several candidate destinations, which is how the model avoids double-counting flows.

Route accounts report flows, costs, and unutilized access.

## 11. Accounts and reporting

Accounts aggregate features and products over fragments, blocks, or groups. The account types are:

- **Summary** — a weighted sum of an attribute.
- **Group summary** — a summary restricted to a block group.
- **Ratio** — a ratio of two summaries.
- **Duplicate** — a scaled copy of another account.
- **Meta** — a combination of accounts.
- **Patch** — a metric over patches, from the spatial subsystem.
- **Route** — a flow or cost over the road network, including exclusive and unutilized variants.

Reports render accounts and target status as tables and charts. The first release targets tabular and
CSV output; chart rendering is a later task.

## 12. Scenario management

A scenario is a named bundle: a set of target settings, an activity (solve, continue, resume, refresh,
or apply-targets-only), a convergence specification, and checkpoint settings. Scenarios can be saved,
reloaded, and run as a set. This is the unit of comparison for analysts.

## 13. CLI and configuration

```text
ws4 build     --xml RECIPE.xml --fragments FRAGMENTS.shp --out build/compiled
ws4 validate  --dataset build/compiled
ws4 simulate  --dataset build/compiled --schedule SCHEDULE.csv --years 200 --out out/sim
ws4 optimize  --dataset build/compiled --targets TARGETS.yaml --weights WEIGHTS.yaml \
              --threads 32 --time-limit 02:00:00 --seed 42 --out out/runA
ws4 report    --run out/runA --out out/report
```

Configuration is file-based (YAML for targets and weights; XML for the recipe). Every command writes a
run directory with its inputs, its seed, and its outputs.

## 14. Performance and HPC

The target host is a two-socket node (2 × Xeon Gold 6254, 72 logical CPUs, two NUMA nodes, 754 GB RAM)
with an NVIDIA RTX PRO 6000 Blackwell (96 GB). The substrate is in
`notes/design/ws4-optimization-stack.md`, section 5:

- Columnar storage and vectorized kernels over fragments.
- A NUMA-aware process pool for parallel scenarios and islands, with per-worker seeds.
- Island metaheuristics that exchange elites asynchronously.
- GPU move evaluation by tensorizing the hot operators (PyTorch first; CPU fallback).
- Parallel math-heuristics: concurrent MIP subproblems and a MIP lane for bounds and warm starts.
- Python-first prototypes, with measured bottleneck kernels ported to C++ behind a stable Python API.
- Checkpointing so long runs survive interruption.
- A hot path free of per-block Python object churn.

## 15. Module layout and interfaces

| Module | Responsibility |
| --- | --- |
| `ws4/model/types.py` | canonical types and the manifest |
| `ws4/io/` | recipe and inventory readers |
| `ws4/build/` | compilation to the matrix dataset |
| `ws4/sim/` | annual simulation |
| `ws4/opt/` | goal programming and the search |
| `ws4/patch/` | topology, patches, core and edge |
| `ws4/roads/` | network, access, haul cost, routing |
| `ws4/cli.py` | the command-line surface |

The current skeleton has two known gaps: `ws4/cli.py` imports a `ws4.build.compiler` module that does
not exist, and the subpackages lack `__init__.py` files. Both are fixed in P1/P2.

## 16. Reproducibility and validation

- The manifest records source hashes and compile options; `validate` checks a dataset against it.
- The simulator is deterministic given a schedule and the compiled dataset.
- The optimizer records its seed, its configuration, and its checkpoints.
- Run directories are self-describing, so a result can be reproduced and audited.

## 17. Open questions

1. **Optimization method.** The metaheuristic is a deliberate first choice. If targets are mostly
   linear and the spatial constraints are light, an exact or LP-relaxation approach may be better for
   a subset of problems. This is revisited in P3.
2. **Recipe schema coverage.** The XML recipe is currently parsed schematically. Its full grammar and
   its validation rules are fixed in P1.
3. **Block aggregation cost.** Summing fragments to blocks every year may dominate runtime on large
   landscapes; a cached incremental aggregate may be needed.
4. **Spatial constraint expressiveness.** Which constraints are first-class (maximum opening size,
   green-up, adjacency) versus user-supplied predicates is settled in P1.
5. **Curve representation.** Per-track curves are stored long-form; the runtime may want a compact
   in-memory form. The trade-off is measured in P2.
