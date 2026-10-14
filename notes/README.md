# Notes

Working notes for WS4. Notes are living: update them in the same change set as the work they describe.

## Layout

- `adr/` — architecture decision records. One decision per file. Never rewrite an accepted ADR;
  supersede it with a new one.
- `design/` — scope, architecture, and focused design notes.
- `reports/` — phase close-out reports.

## Index

- `design/ws4-scope.md` — problem statement, users, scope, and success criteria.
- `design/ws4-architecture.md` — the architecture design.
- `design/ws4-optimization-stack.md` — the optimization stack and the execution substrate.
- `design/ws4-matrix-builder-and-interop.md` — the ForestModelXML recipe, the matrix builder, and legacy ingestion.
- `adr/0001-fragment-compilation.md` — fragments are the compilation unit; blocks are a runtime aggregate.
- `adr/0002-columnar-matrix-dataset.md` — the compiled dataset is versioned and columnar.
- `adr/0003-spatial-structure-first-class.md` — spatial structure is part of the model.
- `adr/0004-goal-programming-metaheuristic.md` — optimization uses weighted goal programming with a parallel metaheuristic search.
- `adr/0005-annual-simulation-step.md` — the simulator steps annually; periods are reporting intervals.
- `adr/0006-xml-recipe-and-matrix-contract.md` — an XML recipe compiles a fragment inventory into the matrix contract.
- `adr/0007-layered-optimization-stack.md` — the optimization stack is layered and pluggable, and generalized from the lab toolkit.
- `adr/0008-python-first-cpp-kernels.md` — Python first, with C++ kernels behind a stable API for profiled bottlenecks.
- `adr/0009-parallel-gpu-execution.md` — parallel and GPU execution strategy.
- `adr/0010-telemetry-meta-portfolio.md` — telemetry-driven tuning and a meta-meta-heuristic portfolio.
- `adr/0011-forestmodelxml-and-legacy-ingestion.md` — adopt the established ForestModelXML format and support legacy datasets.
- `adr/0012-file-and-programmatic-paths.md` — two model-construction paths, file-based and programmatic.
