# Notes

Working notes for WS4. Notes are living: update them in the same change set as the work they describe.

## Layout

- `adr/` — architecture decision records. One decision per file. Never rewrite an accepted ADR;
  supersede it with a new one.
- `design/` — scope, architecture, and focused design notes.
- `reports/` — phase close-out reports.

## Index

- `backlog.md` — the consolidated list of what is not done, kept current with the roadmap.
- `functional-test.md` — the full end-to-end check over a complete sample model.
- `acceptance.md` — the P3.1 acceptance-check results.
- `performance.md` — the P3.5 compile and simulate benchmarks.
- `review-cadence.md` — the review cadence and the first review (P5.1).
- `triage.md` — the issue labels, routing rules, and triage cadence (P5.2).
- `dependencies.md` — dependency and security maintenance policy (P5.3).
- `sync-checklist.md` — the roadmap/backlog/changelog sync checklist (P5.4).
- `release-policy.md` — the version scheme, release cadence, and patch policy (P5.5).
- `handover.md` — the maintainer and handover guide (P5.6).
- `packaging.md` — the P3.6 clean-checkout install, command line, and docs results.

- `design/ws4-scope.md` — problem statement, users, scope, and success criteria.
- `design/ws4-architecture.md` — the architecture design.
- `design/ws4-optimization-stack.md` — the optimization stack and the execution substrate.
- `design/ws4-matrix-builder-and-interop.md` — the ForestModelXML recipe, the matrix builder, and legacy ingestion.
- `design/ws4-performance.md` — the post-release performance and scalability plan (profiling, bottlenecks, targets).
- `design/ws4-curve-grid.md` — the shared age-grid curve-table spike (data-layout change for the numeric core).
- `design/ws4-join-rebuild.md` — the fast fragment-to-feature join rebuild spike (cold-path cost).
- `design/ws4-incremental-route-accounts.md` — incremental route accounts in the objective (spike).
- `design/ws4-construction.md` — faster simulator construction (spike).
- `design/ws4-route-record.md` — faster route-record accumulation (spike).
- `design/ws4-spatial-scoped.md` — adjacency-scoped spatial constraints (spike).
- `design/ws4-builder-perf.md` — faster matrix builder (spike).
- `design/ws4-watch.md` — the live target-window watcher (`ws4 watch`).
- `design/ws4-c5-evenflow-performance.md` — the P83 c5 seeded even-flow performance plan
  (startup, delta state, bounded LNS, seeded islands, GPU batch path).
- `design/ws4-gpu-search.md` — the P83.6 GPU-native batch/population search design.
- `design/ws4-gpu-population-search.md` — the P83.8 candidate-index GPU population search plan.
- `design/ws4-metaheuristic-portfolio.md` — the P83.9 SA/tabu/ILS/GA/LNS master/worker portfolio plan.
- `reports/p83-8-gpu-population.md` — the P83.8 candidate-index population search, c5 2k and TSA23 5k benchmarks.
- `reports/p83-7-full-tsa23.md` — the full-model TSA23 20 x 10 GPU population run and exact replay.
- `reports/p83-closeout.md` — phase close-out: c5 policy result, GPU search, population, and portfolio findings.
- `design/ws4-optimizer-core.md` — event chains and per-move objective deltas (proposed).
- `design/ws4-hydrology-consumer-hardening.md` — P62 preflight, exposure, and optimizer-boundary plan.
- `design/ws4-carbon.md` — historical P58 carbon design note; the current contract is
  `docs/reference/carbon.rst`.
- `reports/p120-multi-boundary.md` — split-TSA production packages and full-landscape
  carbon evidence.
- `reports/carbon-docs-audit.md` — carbon documentation audit and remediation record.
- `reports/carbon-ledger-performance.md` — per-block SIT filtering and the 500-block
  ledger benchmark.
- `reports/carbon-500block-tradeoff.md` — 500-block TSA46 max-stock/min-emissions
  searches, default and high-displacement HWP, with exact replay.
- `reports/greedy-seeding-performance.md` — parallel/deadline-aware floor seeding and
  the 500-block no-warm-start smoke.
- `reports/carbon-harvest-frontier.md` — 500-block high-displacement yield/emissions
  frontier with exact replay.
- `reports/carbon-4tsa-hwp-production.md` — full-landscape TSA08/16/40/41 HWP carbon
  sweep.
- `reports/carbon-4tsa-hwp-sensitivity.md` — low/default/high HWP sensitivity across
  the four TSAs.
- `reports/carbon-tsa41-500-optimization.md` — bounded TSA41 carbon-aware optimization
  and exact verification.
- `reports/carbon-tsa41-5k-optimization.md` — 5k production-scale carbon search,
  initial-state precompute, and the LNS cost finding.
- `reports/carbon-tsa41-5k-200-iterations.md` — 200/500-iteration TSA41 5k carbon
  search, yield-floor frontier, and exact replay.
- `reports/carbon-tsa41-5k-removal-ga.md` — exact removal-effect table, GPU
  population search, and full TSA41 scale result.
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
