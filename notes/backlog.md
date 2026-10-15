# Backlog

Living list of what is **not done**, so nothing is lost. Each item names its area, its status, its
evidence, and its **target phase**. Update this in the same change set as the work it describes. The
roadmap (`ROADMAP.md`) and the GitHub issues are the plan of record; this note is the consolidated gap
list.

Status values: `open`, `partial`, `blocked`, `done`, `out of scope`, `deferred`.

Target phases: `P4` (release and deploy), `P5` (operate and maintain), `post-release` (a future build
phase, to be created), or a named condition.

## Triage summary (P3.7)

Nothing here is release-blocking: every in-scope success criterion is met by P3.1 to P3.6. The open
items are enhancements and maintenance.

- **P4:** none open (the subsystem docs landed in P4.4).
- **P5:** broaden `mypy` coverage to `ws4/`.
- **post-release:** the wider expression library; succession and `produce` semantics; legacy-ingestion
  coverage; a reference replay; the wider operator set and ALNS; the shared solver-core package; the
  island model and GPU moves; time-boxed MIP subproblems; the tuners and the portfolio layer;
  incremental routing for the optimizer objective; core-area rules and edge contrast; duplicate and
  meta accounts and chart output; unit conversion; and the topology stub cleanup.
- **Blocked:** the MKRF canonical artifacts' location log is not on `origin` (the objects are on
  `arbutus-s3`); a fresh clone needs the producer to push the git-annex branch.
- **Deferred:** the block-aggregation cache (not the hot path).

## Matrix builder (P2.1)

- **Expression language.** `done` (bounded). Select statements evaluate with `ws4/io/expressions.py`:
  comparisons (`eq/ne/lt/le/gt/ge/in`), booleans (`and`/`or`/`not`), parentheses, string concatenation
  and arithmetic, and the functions `startswith`, `endswith`, `substring`, `int`, `Number`, `length`,
  `if`, `lastindexof`, `lookupTable`, `curveId`, `attribute`, and `operable`. A curve reference
  (`curveId`/`attribute`) survives scaling and offsetting arithmetic, so a derived curve keeps the base
  curve's identity; `operable(x)` is an identity here (masking is a runtime concern); and an expression
  that evaluates to a number becomes a constant curve. An expression the evaluator cannot parse falls
  back to the term matcher. Remaining: the wider function library. Target: post-release.
- **Expression-sourced attribute curves.** `done`. An `<attribute>` with an `<expression>` (for example
  `curveId('Yield_'+au)`) is evaluated per stratum to a curve name and resolved against the recipe's
  curves. The evaluator handles `curveId`, `attribute`, `lastindexof`, string concatenation, and
  arithmetic. The `<curve idref>` form and the `treatment eq 'X'` product context match the reference.
- **`%f` / `%m` / `%au` label tokens and `factor` expressions.** `done`. The `%f` (feature/product),
  `%m` (managed/unmanaged), `%au`, and `%s` tokens expand per stratum; an expression label such as
  ``'%f.area.%m.state.'+if(...)`` is evaluated after substitution; and a `factor` expression scales the
  attribute's curve into a derived curve (reused per base curve and factor).
- **Account and feature/product de-duplication.** `done`. The builder writes a summary account for every
  attribute (the `protoaccounts` table), grouped by the managed state of the producing selects
  (`_MANAGED_`, `_UNMANAGED_`, `_ALL_`), and matches the reference `protoaccounts.csv` exactly on all
  nine core variants.
- **Protoaccounts vs accounts.** `done`. The matrix builder emits `protoaccounts`; the user copies it to
  `accounts` and edits it. Re-running regenerates `protoaccounts` but must not overwrite the edited
  `accounts`. (The 47 extra labels in one reference `accounts.csv` were a user edit removing a species
  with no share — not a builder rule.)
- **Overlay/scenario variants.** `out of scope`. The `overlay_*` variants are a modelling convention for
  one instance family, not a format feature; their `output/` recipes are reduced exports that do not
  correspond to the `tracks_overlay_*` matrices.
- **Succession and `produce` semantics.** `partial`. `<transition>` is applied; `<succession>` and
  `<produce>` are parsed only as far as treatments need. Target: post-release.
- **Intensive treatment lanes.** `done`. The intensive variants (CT, PCT, F1-F3) match the reference
  exactly. The fix was canonicalizing integral floats (`985502002.0` to `985502002`).
- **Numeric vs literal matching.** `done`. State values are formatted canonically; an integral float is
  rendered without a decimal part.
- **Full MKRF canonical model.** `done`. The canonical artifacts were materialized on 2026-10-15
  (SHA-256 verified against the producer's), and the builder now reproduces the canonical matrix
  **exactly** — tracks 7048/7048, strata 7048/7048, treatments 10014/10014, blocks 3183/3183, features
  104311/104311, products 420588/420588, and protoaccounts 91/91 (row counts and label sets;
  `scripts/acceptance.py`). Earlier fixes covered `lookupTable`, expression-based `<define column>`
  values, a literal retention factor, and label/product expressions without `%` tokens. The last five
  labels closed the gap: a `<features>` element nested inside `<retention>` is parsed and attaches to the
  retained stratum (`feature.area.retention.total`); `operable(...)` and `attribute('label')` resolve an
  attribute against the labels already emitted for a stratum (`feature.yield.managed.merch.total`); a
  curve reference survives scaling and offsetting arithmetic; and an expression that evaluates to a
  number becomes a constant curve (`product.Cost_Silviculture`/`Cost_Total`/`NetRevenue`). The producer's
  git-annex branch was not pushed to `origin`, so a fresh clone cannot `get` the artifacts (a `reinject`
  workaround was used locally); the four objects are on `arbutus-s3` and only the location log is missing.
- **Shapefile input.** `done`. `ws4/io/fragments.py` reads a shapefile, GeoJSON, GeoPackage, CSV, or
  Parquet (attributes; geometry is available separately). The geo dependency is imported lazily, and CI
  installs the `geo` extra.
- **Expression-based input fields.** `done`. An ``<input>`` expression such as ``Int(RES_KEY)`` or
  ``Shape_Area/10000`` is evaluated against the fragment row.
- **Legacy matrix ingestion coverage.** `partial`. `ws4 ingest` maps the known legacy columns; other
  legacy layouts and the road model are not covered. Target: post-release.

## Simulation (P2.2)

- **Operability and eligibility evaluation.** `done`. A scheduled treatment applies only where the
  fragment's track offers it (the Model II rule).
- **Succession and track switching during a run.** `done`. A treatment moves the fragment to its
  `new_track` and resets its offset.
- **Product yields.** `done`. Applying a treatment records the product yield (area times the product
  curve at the pre-treatment offset) to `product_values.csv`.
- **Route flows.** `done`. With a road network, each produced product is routed to the block's nearest
  destination and written to `route_values.csv` with its length and cost.
- **Patch metrics over blocks.** `done`. `ws4/patch/metrics.py` groups the disturbed blocks into
  connected patches over the topology and reports the count, mean size, largest opening, and size-class
  distribution; the simulator writes `patch_metrics.csv` when given a topology.
- **Deterministic replay test.** `done` (two runs are identical; an unoffered treatment is a no-op).
  A replay validated against a reference run remains open. Target: post-release.

## Optimization and solver (P2.3-P2.6)

- **Objective and targets.** `done`. Weighted goal programming (`ws4/opt/objective.py`): per-year minimum
  and maximum with weights; targets load from YAML.
- **Operator registry and metaheuristics.** `partial`. `ws4/opt/operators.py` (toggle, shift, swap, LNS)
  and three solvers in `ws4/opt/solvers.py` — simulated annealing, tabu search, and iterated local
  search — selected by `OptimizeConfig.metaheuristic`, with multi-start (`OptimizeConfig.starts`). All
  seeded and reproducible. Open: ALNS and the wider operator set. Target: post-release.
- **Solver core.** `partial`. The problem-adapter boundary is implemented (`ws4/opt/core.py`: a `Problem`
  with an evaluator, candidate moves, and an operator registry) and the solvers take it. Open: extracting
  a separate shared package for WS4/WS3/FHOPS. Target: post-release.
- **Parallel and GPU execution substrate.** `partial`. Parallel multi-start runs across a process pool
  (`OptimizeConfig.workers`), one seeded start per worker, keeping the best. Open: the island model with
  elite sharing, NUMA-aware placement, and tensorized GPU move evaluation. Target: post-release.
- **Math-heuristic layer (MIP).** `partial`. Destroy-repair large-neighbourhood search is an operator
  (`lns`); a warm start seeds the search from each block's first candidate (`OptimizeConfig.warm_start`);
  and `ws4/opt/mip.py` solves an option-selection MILP (HiGHS via `scipy.optimize.milp`) for a penalty
  **lower bound** and a candidate schedule. `OptimizeConfig.mip_bound` records the bound and the gap.
  Open: time-boxed MIP destroy-repair subproblems. Target: post-release.
- **Telemetry and tuning.** `partial`. `ws4/opt/telemetry.py` writes a JSONL run header and a step record
  per iteration. Open: the tuners and the portfolio layer. Target: post-release.

## Spatial, roads, accounts (P2.7-P2.8)

- **Block topology and patch metrics.** `done` (metrics). The topology loader and patch metrics are
  implemented and verified against an independent calculation (P3.4). `ws4/patch/topology.py` is a stub
  that duplicates the loader. Target: post-release.
- **Spatial-constraint enforcement.** `done`. `ws4/patch/constraints.py` reports the largest opening per
  year, opening violations, green-up violations, and a combined penalty; the simulator writes
  `spatial_violations.csv`; and the optimizer adds a weighted spatial penalty, disabled by the explicit
  `allow_spatial_override`. Open: core-area rules and edge contrast. Target: post-release.
- **Road network, access, haul cost, exclusive routing.** `done`. `ws4/roads/network.py` routes over
  the segment graph (least-haul-cost route, shortest length and cost, nearest destination), and a
  destination is identified by its **account name** (several destinations may share a vertex). The
  route model (`ws4/roads/accounts.py`) chooses an exclusive destination per product per block by
  eligibility, with an optional unutilized (surplus) account, and the route cost ledger accumulates
  the haul, build (charged once), and maintenance (charged per period used) costs. The simulator
  writes `route_values.csv`, `network_table.csv`, `route_table.<destination>.csv`, and the
  `route_cost_report.csv`. Route accounts (`RouteAccount`) and duplicate accounts
  (`DuplicateAccount`) are resolved into the account values (`resolve_account_values`), so the
  optimizer can target accounts such as `route.Total.haul`; a route configuration YAML
  (`load_route_config`) names the tables, eligibility, and accounts. Open: the route model runs in
  the optimizer's inner loop, so each evaluation routes every scheduled block (a future
  incrementality optimization), and core-area and edge-contrast rules. Target: post-release.
- **Patch accounts.** `done`. `ws4/patch/accounts.py` implements the patch size-class sub-accounts
  (area, size, shape, frequency, attractor) over the block topology for a criteria feature and a
  threshold; the criteria value per block is derived from a feature curve
  (`Simulator.block_criteria`), and the simulator writes `patch_accounts.csv`. The topology loader
  accepts the established `BLOCK1,BLOCK2,DISTANCE,LENGTH` columns with the `-9999` sentinel.
- **Account types and reports.** `partial`. `ws4/report.py` summarizes accounts, evaluates a ratio
  account, reports target status, and writes `report_accounts.csv` / `report_targets.csv`. Open:
  duplicate and meta accounts, and chart output. Target: post-release.
- **Unit conversion (map vs report units).** `open`. Target: post-release.

## Programmatic model API (P2.9)

- **Model object and operations.** `done`. `ws4/model/api.py` holds one DataFrame per matrix table with
  `append` and `replace`.
- **Load from / write to the matrix; round-trip equality.** `done`. `Model.from_dataset` and
  `Model.write` round-trip a dataset (valid, same table lengths), and an empty model writes a valid
  dataset.

## Tooling and process

- **Shapefile/geo extra in CI.** `done`. CI installs `.[geo]`, and `tests/test_fragments.py` covers a
  shapefile read (skipping when geopandas is absent).
- **Broaden mypy coverage to `ws4/`.** `open`. Type checking covers `scripts/`, `tests/`, and
  `docs/conf.py` plus transitively imported modules. Target: P5.
- **Reference-matrix regression tests.** `done`. A self-contained fixture with committed expected tables
  is in `tests/fixtures/matrix/`, compared by `tests/test_matrix_regression.py` (P3.3).
- **Block-aggregation cost.** `deferred`. The C5 profile shows the per-curve yield evaluation dominates
  the simulator, so a cached incremental block aggregate is not needed yet (`notes/performance.md`).
  Target: post-release, if profiling shows it.
- **Docs for each subsystem.** `done`. The compiled dataset, ForestModelXML, simulator, optimizer,
  spatial, and road pages exist under `docs/reference/`, and the API pages cover the tooling.
