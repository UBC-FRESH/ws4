# Research paper ideas: benchmark reproduction and a generic solver

Status: idea capture only
Date: 2026-11-01

These are candidate research directions, not an approved plan. Another session owns the
detailed paper/benchmark plan; this note preserves the ideas and the intended framing so
they are not lost.

## Paper A: spatially explicit harvest scheduling benchmarks

### Candidate comparisons

Reproduce published benchmark instances and results from spatially explicit,
landscape-level forest harvest scheduling, especially heuristic/metaheuristic work:

- Lockwood and Moore (1993), a classic spatially explicit harvest-scheduling benchmark.
  Verify the exact instance, constraints, objective, reported solution quality, and
  hardware/run-time basis before claiming a comparison.
- Other spatially explicit landscape-level heuristic harvest-scheduling papers with
  reproducible instances or enough published detail to reconstruct them.
- Conservation-oriented landscape optimization from Tara Martin's lab and related
  systematic-conservation-planning literature, where the objective is spatial
  prioritization or landscape configuration rather than timber volume alone.

The first task for each candidate is **reproducibility triage**:

- is the instance public, or reconstructable from the paper?
- are the constraints and objective unambiguous?
- is the reported solution quality and run time reproducible on a defined machine?
- is the published comparator a heuristic, an exact solve, or a planning workflow?

Do not compare wall-clock numbers without normalizing hardware, language, parallelism,
precision, and stopping rules.

### Claim to test

The contribution is not “GPU goes brrr.” The candidate contribution is the **system
architecture pattern**:

```text
compiled model/effect tables
  + compact candidate chains
  + batched GPU pricing
  + hybrid local search
  + resident state/display
```

The benchmark result is evidence that this architecture can reproduce or improve published
landscape-scale spatially explicit solutions at much lower wall-clock time, while remaining
exact under the declared model contract.

Benchmark destruction is the entertaining result; the architecture is the thesis.

### Required evidence

- Same constraints and objective as the source, or an explicit, justified deviation.
- Exact objective/feasibility checks, not only GPU-prerendered scores.
- Seed/replicate reporting, not a single cherry-picked run.
- Wall-clock decomposition: launch, table/cache load, search, verification.
- Hardware and software versions.
- Reproducible scripts and published inputs.

## Paper B: `fresh-solutions`, a generic metaheuristic engine

Generalize the WS4 search engine into a model-agnostic open-source solver, tentatively
`fresh-solutions`:

- a small problem interface for variables, candidate moves, objective evaluation, and
  constraints;
- batched GPU evaluation for compatible problem classes;
- CPU fallback and hybrid local search;
- resident state and streaming diagnostics;
- benchmark adapters for public combinatorial-optimization instance libraries.

Candidate benchmark families should be chosen for reproducibility, not prestige. Public
mixed-integer, routing, scheduling, packing, graph, and satisfiability-style libraries are
obvious starting points; each needs a licensing and instance-format review.

The paper should not claim universal superiority. The interesting result is the boundary:

- where does batched GPU search beat conventional heuristics?
- where does the architecture lose because of table construction, memory, or irregular
  constraints?
- what class of problems benefits from resident state plus hybrid local search?

## Relationship to the GPU cache issue

The interactive target-editing problem in
`gpu-effect-cache-interactivity.md` matters for the product, but a paper benchmark can use a
frozen target/account basis. Keep those claims separate:

- **paper benchmark:** fixed scenario, one expensive table build, many search runs;
- **production product:** analyst changes targets and watched accounts while the solver is
  running, with no hour-long rebuild.

Do not let the frozen-benchmark result imply the interactive product is solved.

## Open questions

- Which 1993 Lockwood–Moore instance and result is the actual literature comparator?
- Which modern spatially explicit harvest-scheduling papers publish reproducible
  instances rather than only maps and summary tables?
- What conservation-planning benchmarks are public and comparable to harvest scheduling?
- What public combinatorial libraries permit redistribution of derived results?
- What hardware baseline is fair for comparisons: CPU-only, one GPU, or a normalized
  cost-per-solve?
- What is the minimum reproducible artifact set: instance, target/constraint file,
  schedule, exact verification, and timing log?

## Next action elsewhere

The other session owns the detailed benchmark selection, paper structure, and external
collaboration plan. This note should be updated with citations and a reproducibility
matrix before any public claim is made.
