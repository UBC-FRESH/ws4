# Notes

Working notes for WS4. Notes are living: update them in the same change set as the work they describe.

## Layout

- `adr/` — architecture decision records. One decision per file. Never rewrite an accepted ADR;
  supersede it with a new one.
- `design/` — scope, architecture, and focused design notes.
- `plans/` — multi-task phase plans that are too long for the roadmap.
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
- `design/ws4-stochastic-landscape.md` — the P144 design that joins deterministic estate
  optimization with stochastic spatially explicit landscape processes in one event engine.
- `design/ws4-fire-3d-visualization.md` — queued idea: synthetic individual-tree stands over
  real VRI polygons and a real-time 3D fire/smoke viewer.
- `design/ws4-fire-behaviour.md` — the P156 Rothermel surface-fire kernel, contracts, and
  standard-case validation plan.
- `design/ws4-fire-validation-ladder.md` — published validation statistics, decision-grade
  benchmarks, and the P163/P164 plan.
- `design/ws4-public-fire-corpus.md` — the P165 depth/breadth/model-only corpus contract and
  the two-fire data gap.
- `reports/p163-closeout.md` — P163 behaviour classes, spotting, 3D outcomes, and accepted
  proxy limits.
- `reports/p165-corpus-inventory.md` — P165.1 candidate inventory and the blocked corpus gate.
- `design/ws4-open-fire-model-reuse.md` — Planscape/burn-emulator review, the observed-fire
  calibration gap, and the bounded P159 surrogate plan.
- `reports/p159-corpus-manifest.json` — P159.1 deterministic synthetic corpus metadata and
  train/validation split.
- `reports/p159-model-card.md` — P159.2 surrogate architecture, training data, losses, and
  limitations.
- `reports/p159-evaluation.md` — P159.3 held-out synthetic and Dogrib OOD evaluation.
- `reports/p159-closeout.md` — P159 no-go integration decision and retained artifacts.
- `design/ws4-second-fire-calibration.md` — P161 data gate, the selected Hay River/K'atl'odeeche
  2023 fire, and the calibration/holdout constraints.
- `design/ws4-fire-calibration-protocol.md` — P161.3 pre-registered parameters, objective,
  search grid, decision rule, and Dogrib holdout.
- `reports/p161-closeout.md` — P161 no-go: the Hay River grid saturated the domain and the
  multipliers had no effect.
- `reports/p162-sensitivity.md` — day-window sensitivity evidence for the Hay River
  calibration.
- `reports/p162-closeout.md` — P162 no-go: the model is sensitive but still far above observed
  growth at every registered point.
- `design/ws4-optimization-stack.md` — the optimization stack and the execution substrate.
- `design/weighted-goal-programming-aspirations.md` — targets are weighted aspirations, not hard bounds; maximum even-flow harvest and priority-tier caveats.
- `design/gpu-effect-cache-interactivity.md` — target-independent GPU cache basis, lazy column extension, and live target editing.
- `design/factorized-account-basis.md` — P88 structural account basis, padded device layouts, one-account lookups, and target switching.
- `design/research-paper-ideas.md` — benchmark-reproduction and generic-solver paper ideas; planning only.
- `design/ws4-matrix-builder-and-interop.md` — the ForestModelXML recipe, the matrix builder, and legacy ingestion.
- `design/ws4-fast-startup.md` — P84 resident Model II startup and state-watch plan.
- `design/ws4-performance.md` — the post-release performance and scalability plan (profiling, bottlenecks, targets).
- `design/ws4-ui-port-plan.md` — phased UI ports from FHOPS, Urban Forest Lab, and HectaresBC.
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
- `reports/p88-factorized-gpu.md` — the P88 full TSA24 factorized feature/product pricers, mixed account switch, and memory evidence.
- `reports/p89-mixed-target-search.md` — the P89 full TSA24 mixed-target population, corrected stock-account evidence, and watcher display path.
- `reports/tsa24-ltsy-allperiods5.md` — candidate all-period ±5% LTSY scenario with a 90% final managed-stock floor and a 5,000-generation probe.
- `reports/tsa24-ltsy-scenario-comparison.md` — baseline vs all-period ±5% LTSY at the same seed and 5,000-generation budget.
- `reports/p95-factorized-target-cell-vectors.md` — target-cell vectors cut the stock-floor search from 219 s to 44 s.
- `reports/tsa24-ltsy-base-profile.md` — default all-period ±5% LTSY profile with the managed-stock guard.
- `reports/tsa24-mixed-vector-performance.md` — P97 11-cell mixed target vector benchmark: 12.9 -> 609 genomes/s.
- `reports/tsa24-ltsy-profiles.md` — named baseline/base/nostock LTSY profiles and the watcher selector.
- `reports/tsa24-profile-ui.md` — web profile library API and Targets-tab selector.
- `reports/tsa24-ask-overlay.md` — floating header Ask pill and assistant overlay.
- `reports/tsa24-profile-runs.md` — profile-aware GPU run worker and web run API.
- `reports/tsa24-profile-run-feedback.md` — live schedule diffs and final account replay for profile runs.
- `reports/tsa24-profile-target-telemetry.md` — profile-run target values and yearly series.
- `reports/tsa24-profile-run-reports.md` — profile-run account/target/ending reports.
- `reports/p114-prices.md` — the `prices.v1` scenario price-path reader, comparison, and provenance report.
- `reports/tsa27-gpu-profile.md` — factorized-optional TSA 27 s8 GPU profile.
- `reports/tsa29-gpu-profile.md` — table-backed TSA 29 base GPU profile.
- `reports/tsa24-map-fallback.md` — geometry capability and map-unavailable state.
- `reports/tsa24-source-geometry.md` — real source polygons and regeneration notes.
- `reports/p125-playback-map-race.md` — playback serialization and stale map response guard.
- `reports/p127-target-chart-solve.md` — target chart row selection and Solve semantics.
- `reports/p128-target-chart-table-sync.md` — chart edits and table input synchronization.
- `reports/p129-gpu-current-targets.md` — GPU profile target override and time budget.
- `reports/p131-profile-time-budget.md` — time budget overrides profile generations.
- `design/ws4-pareto-explorer.md` — P136 point-cloud contract and 3D explorer.
- `reports/p136-solution-space.md` — exact full-member solution-space payload and browser smoke.
- `reports/p130-solve-gpu-profile.md` — Solve routing through the GPU profile path.
- `reports/tsa24-map-performance.md` — bounds sidecar and overview layer.
- `reports/p83-8-gpu-population.md` — the P83.8 candidate-index population search, c5 2k and TSA23 5k benchmarks.
- `reports/p83-7-full-tsa23.md` — the full-model TSA23 20 x 10 GPU population run and exact replay.
- `reports/p83-closeout.md` — phase close-out: c5 policy result, GPU search, population, and portfolio findings.
- `reports/p83-lean-table.md` — lean effect-table archive and the full TSA23 4x end-to-end result.
- `reports/p83-candidate-cache.md` — simulator/candidate caches and the full TSA23 11x end-to-end result.
- `reports/p83-gpu-session.md` — resident session reuse across repeated full-model seeds.
- `reports/p83-gpu-matrix.md` — ten-seed full TSA23 GPU matrix and exactness-comparison fix.
- `design/ws4-optimizer-core.md` — event chains and per-move objective deltas (proposed).
- `design/ws4-hydrology-consumer-hardening.md` — P62 preflight, exposure, and optimizer-boundary plan.
- `plans/ws4-sdmd-au-explorer.md` — P87 plan: schema, ingestion, SDMD digitisation, regimes, API, web tab, and solver constraints.
- `reports/p87-closeout.md` — Phase 87 SDMD and AU Explorer close-out, queued for approval.
- `reference/bc-sdmd-sources.md` — the 14 public BC SDMDs, their BEC coverage, and the caveats.
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
- `adr/0013-sdmd-as-constraint-layer.md` — the SDMD layer is diagnostic and a constraint source, not a growth model.
- `reports/p84-state-watch.md` — resident Model II state watcher on the c5 sample.
- `reports/p138-pareto-to-plan.md` — P138 member promotion and outcome-front alignment.
- `reports/p139-target-faithful.md` — P139 run-local targets for promoted members.
- `reports/p140-target-dimensions.md` — P140 periodic target dimensions in the scan builder.
- `reports/p141-portfolio-target-prep.md` — P141 level-only targets and initial schedules.
- `reports/p142-default-stock90.md` — P142 generated stock-guarded default scenarios.
- `reports/p143-web-trust.md` — P143 cache, artifact, promoted-target, and profile cleanup.
- `reports/p144-closeout.md` — P144 stochastic landscape engine verification and close-out.
- `reports/p145-multi-account-targets.md` — P145 multi-account portfolio target scaffold.
- `reports/p146-live-multi-account-scan.md` — P146 five-account TSA27 browser validation.
- `reports/p147-diverse-scaffold.md` — P147 diverse account preset and warnings.
- `reports/p148-portfolio-cleanup.md` — P148 guarded cleanup for artifacts and promoted runs.
- `reports/p149-state-exactness.md` — P149 state-run exactness and UI badge.
- P149.2 records the compact exactness payload and the live exact replay.
- `reports/p150-gpu-extension-guard.md` — P150 lazy effect-table row guard and the TSA 29
  managed-stock limitation.
- `reports/p151-web-console.md` — P151 allowlisted web console, its security boundary,
  browser smoke, and the remaining sandbox tiers.
- `reports/p152-python-sandbox.md` — reviewed Python scripts under Landlock and unshare,
  with the host-read, write, network, and credential checks.
- `reports/p153-assistant-script-review.md` — assistant script staging, review requirements,
  and the console-secret environment guard.
- `reports/p154-tsa29-stock.md` — TSA 29 factorized stock basis, build costs, and exact
  GPU replay.
- `reports/p155-closeout.md` — P155 fire-scene verification, visual checklist, limits, and
  approval status.
- `reports/p158-plan-matrix.md` — Plan scenario matrix, observed usability gaps, and the
  next scenario-authoring slices.
- `reports/p158-batch-composer.md` — P158.3 multi-account and period-range target authoring.
- `reports/p158-scenarios.md` — named Plan scenarios, reload-live, and target diffs.
- `reports/p158-penalty-ledger.md` — Plan objective composition, binding ranks, and flow
  penalties.
- `reports/p158-closeout.md` — Plan scenario workspace verification, tablet limits, and phase
  close-out.
- `reports/p160-dogrib-matrix.md` — burning-condition and WindNinja 2c/2d evidence; the
  threshold gate does not change 2b, and the WindNinja grids underburn.
- `reports/p160-closeout.md` — P160 close-out, accepted limits, and the next-fire
  calibration recommendation.
