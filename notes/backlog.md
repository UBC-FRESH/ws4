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
  island model and GPU moves; time-boxed MIP subproblems; the tuners and the portfolio layer; duplicate
  and meta accounts and chart output; unit conversion; and the topology stub cleanup.
- **Blocked:** the MKRF canonical artifacts' location log is not on `origin` (the objects are on
  `arbutus-s3`); a fresh clone needs the producer to push the git-annex branch.
- **Deferred:** the block-aggregation cache (not the hot path). Native kernels (P6.6) are **adopted**
  (a numba product-gather kernel, ~1.1× end-to-end, exact parity, Python fallback; CI installs numba).
  See `notes/design/ws4-performance.md`.

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
  curve at the pre-treatment offset) to `product_values.csv`, and the year's products are summed into
  the account values (one row per year and account), so the optimizer scores a target on a `product.*`
  account.
- **Route flows.** `done`. With a road network, each produced product is routed to the block's nearest
  eligible destination and written to `route_values.csv` with its length and cost. What is *delivered*
  is what an eligibility map names: a product the map does not name is routed nowhere, because a
  configuration that says where wood goes is saying what the wood is (P12.3, #123 — it had been routing
  the areas, the sera classes and the volume classes to the mills beside the yield, which made the route
  report's volume 2.26× the reference's).
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
  year, opening violations, green-up violations, core-area violations, and a combined penalty; the
  simulator writes `spatial_violations.csv`; and the optimizer adds a weighted spatial penalty
  (opening, green-up, and core-area), disabled by the explicit `allow_spatial_override`.
- **Core-area rule.** `done`. `core_area` (in `ws4/patch/metrics.py`) removes a buffer strip around a
  patch perimeter; `core_area_violations`/`core_area_penalty` (in `ws4/patch/constraints.py`) report and
  penalize patches whose core is below a minimum. Wired into the simulator (`core_buffer_m`,
  `min_core_area_ha`) and the optimizer.
- **Edge contrast.** `done`. `edge_contrast` (in `ws4/patch/constraints.py`) sums the shared boundary
  where one side matches the first attribute and the other matches the second, weighted by the shared
  edge length. `ws4/patch/edge.py` loads the edge elements and produces an edge account value per
  period; the simulator writes `edge_metrics.csv` and adds the edge accounts to `account_values.csv`,
  so the optimizer can target them.
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
  (area, size, shape, frequency, blocks, freqpercent) over the block topology for a criteria feature and
  a threshold; the criteria value per block is derived from a feature curve
  (`Simulator.block_criteria`), and the simulator writes `patch_accounts.csv`. The topology loader
  accepts the established `BLOCK1,BLOCK2,DISTANCE,LENGTH` columns with the `-9999` sentinel.
- **Account types and reports.** `partial`. `ws4/report.py` summarizes accounts, evaluates a ratio
  account, reports target status, and writes `report_accounts.csv` / `report_targets.csv`. Open:
  duplicate and meta accounts, and chart output. Target: post-release.
- **Unit conversion (map vs report units).** `open`. Target: post-release. One instance is measured and
  in the route report: WS4 reports `AVERAGEHAULDIST` in **metres** and the reference in **kilometres**, so
  the column reads 1,200× apart when it is 1.2× (P12.3, #123) — converting WS4's own column is a decision
  about its report rather than about the comparison, so it is left for this item rather than done quietly
  under a parity task.
- **What the reference's route report `LENGTH` counts.** `open`, and the one quantity of P12.3's
  comparison left unexplained. It is a segment-set quantity — the length of the distinct road in use
  during a period — and WS4 reports **2.6×** the reference's for MILL 1 and **3.3×** for MILL 2 over the
  twenty periods, where maintenance is *consistent with* it on both sides (1.17 a metre in WS4 against
  0.98 in the reference) and the haul expense is *lower* while more road is in use. So the two runs use
  **different roads**, not different amounts of wood: WS4 routes over the whole planned network (11,606 km
  of 36,721 segments) while the reference's search builds roads as it goes. The candidate explanation —
  that its report counts only the roads its own run has opened — is unverified, and is recorded as a
  candidate rather than asserted.

  Two more readings have since been ruled out from the export itself.
  `scenario/route_destination.MILL*.csv` lists 26,905 rows per mill whose segments sum to **6.6 million
  metres** — 7.4 times the report's mean period `LENGTH` — so those rows walk the **reachable** network
  rather than the road a period used. And a period's `LENGTH` is neither the cumulative `BUILTLENGTH` nor
  monotone in it: `LENGTH` falls from 1,149,647 to 741,466 across periods while the build only grows, and
  1,149,647 is exactly the period's build plus an initial **417,574 metres** that no table in the export
  states. So `LENGTH` is a per-period quantity over a road set the export does not list, which is why it
  is the one column P12 could not settle.

## Programmatic model API (P2.9)

- **Model object and operations.** `done`. `ws4/model/api.py` holds one DataFrame per matrix table with
  `append` and `replace`.
- **Load from / write to the matrix; round-trip equality.** `done`. `Model.from_dataset` and
  `Model.write` round-trip a dataset (valid, same table lengths), and an empty model writes a valid
  dataset.

## Tooling and process

- **Shapefile/geo extra in CI.** `done`. CI installs `.[geo]`, and `tests/test_fragments.py` covers a
  shapefile read (skipping when geopandas is absent).
- **Broaden mypy coverage to `ws4/`.** `done` (P9.6, #102). It was never the work that was missing:
  `mypy ws4` already reported success on all 43 files, and the gate simply did not name them. The
  `files` list now names `ws4` first, so the gate checks **93 files** where it checked 50, and the
  backlog item closes with the evidence rather than staying open behind a stale assumption.
- **Reference-matrix regression tests.** `done`. A self-contained fixture with committed expected tables
  is in `tests/fixtures/matrix/`, compared by `tests/test_matrix_regression.py` (P3.3).
- **Block-aggregation cost.** `deferred`. The C5 profile shows the per-curve yield evaluation dominates
  the simulator, so a cached incremental block aggregate is not needed yet (`notes/performance.md`).
  Target: post-release, if profiling shows it.
- **Docs for each subsystem.** `done`. The compiled dataset, ForestModelXML, simulator, optimizer,
  spatial, and road pages exist under `docs/reference/`, and the API pages cover the tooling.
- **Command-line gaps found while writing the user docs.** `done` (P7.1, #83). `--weights` is optional
  and documented as accepted-for-compatibility, and `ws4 optimize` takes `--iterations`. Applying a
  per-account factor file is a capability worth having only if a study asks for it; it is not.
- **A patch target in a run's report.** `done` (P7.6, #88). The search priced the patch accounts
  correctly — a simulation and the incremental evaluator agreed to the hundredth — but `Optimizer.run`
  replayed its incumbent without passing the patch accounts to the simulation, so the reported share
  was a missing row: zero, carrying the whole penalty. The report now folds `patch_accounts.csv` into
  the values it prices, and a simulation of the same schedule agrees with it.
- **Island scaling past 8 islands.** `open`, narrowed by P9.2 (#99). The limit is memory contention
  rather than BLAS oversubscription (P7.2 measured both: pinning the pools changes nothing, and the
  same 32-island configuration ran at 13x to 16x while the host's load moved between 4 and 65), and the
  candidates are fewer than they looked: a preloaded, forked copy of the dataset shares no state a
  worker uses and costs ~1 s of serial setup, worth about **-12%** at 16 and 32 islands, so it was
  removed. P9.3 and P9.4 go after the per-iteration costs instead.
- **One copy of the dataset for the pool, handed over rather than reloaded.** `open`, no throughput
  claim. A worker builds its own optimiser from the dataset directory (`_island_job`), so the parent's
  built state — the simulator's frames, the candidate chains, ~170 MB per process — cannot help it
  without changing what a worker receives. Doing it properly means handing the pool a read-only built
  state, which is the prerequisite P8.4 named: the simulator writes to the fragments frame it inherits,
  so the shared part has to be genuinely read-only, and the per-island configuration has to survive the
  handover. Worth doing only for memory-constrained hosts: on a 754 GB machine the capacity saves
  nothing, and sharing pages does not reduce bandwidth, since every process reads the same bytes.
- **`Optimizer.last_account_values()` after a `run`.** `done` (P7.5, #87). The incremental value path
  and `run` both record the frame they build, so the incumbent's values are readable without rereading
  the run directory.
- **The per-`(block, chain)` criterion series and the patch state construction.** `done`. Both halves
  of P7.5's lever have been taken. The series was made 29% cheaper (P8.3: 58.6 -> 41.5 us/call, the C5
  patch-ramp workload +21%) by removing the copying, the per-segment `arange` and the per-year Python
  calls, not by vectorising it. The state construction was made 89% cheaper (P9.3: 25.9 -> 2.79 ms per
  state) by building the year-invariant node order, areas and CSR once per group and sharing them,
  which is more than the laziness the note suggested. Building *less* of a state stays rejected, with
  P8.3's reason: the years that get one are already only the accounting points a target reads.
- **Flow targets in `report_targets.csv`.** `done` (P11.3, #115). A flow target is now reported as the
  series the reference reports: one row per period, carrying the period's percent value and priced by
  the same `penalty` the objective uses, with a zero for the period an even-flow comparison is made
  against — which is what the reference's own report holds. Before this, a flow target was priced as a
  level target and could be reported as met while the search was paying for it. Measured against the
  reference's own `targets/flow_*.csv` on both 2026 scenarios: **values matching to four decimals**
  (period 1 at 40.244 on both sides), and the acceptance check now compares **1,383** account-period and
  flow values.
- **A zero flow balance is priced as infinite but reported as satisfied.** `open`, a modelling question.
  Where a flow's balance is empty — the no-treatment scenario, where nothing is harvested — the
  objective prices every period as infinite (`flow_penalty`'s documented behaviour) while the reference's
  report holds **0.0**, i.e. satisfied. A report and the acceptance comparison use the reference's
  reading; whether the *objective* should too is a decision, since a run with an empty period is
  currently penalised without bound.
- **WS4's period convention versus the reference's.** `done` (P11.1, #113). A target now names the year
  its period **ends** on, and it accumulates only if it is a `product.` account; everything else — a
  feature, a patch, a size class's share — is a level read at that year. Pinned from the reference's own
  period values, not inferred: an account it reports as **1,921,975.8** for year 10 is the sum of WS4's
  years 1-10 (**1,921,975.7**), where the old start-labelled window summed years 10-19 (1,461,044.0);
  and its `feature.Area.managed.PL` at year 10 is the level (38,436.2) where WS4 summed ten years of it
  (**384,362.3**, ten times high). The objective, the report, the incremental evaluator, the patch
  accounting points and the MIP bound all follow one rule, `ws4.opt.objective.accumulates()`, and the
  acceptance check states the rule **independently** so the two can disagree.
- **Road maintenance as a function of the traffic a road carries.** `done` (P12.5, #125), behind the
  parity mode. The reading is `f(0) = 0` and `f(x > 0) = b + a x`, chosen by
  `divergences.maintenance`, and its effect is measured on the 2026 base scenario: +4.2% of the
  maintenance at `a = 0.001`, +42.4% at 0.01 and ×5.24 at 0.1, with the haul unchanged. The text below
  is the record of why, kept as written when it was still open. Traffic-weighted maintenance is conceptually
  defensible — it is simply not what the reference does (it charges each used road once for the period),
  and on the 2026 sample WS4's traffic reading was about **170×** the reference's, so parity needs the
  reference's reading (implemented, and the ledger's test pins it: nine times the volume over the same
  segments leaves the maintenance unchanged and grows only the haul). The better metric, as specified by
  the maintainer, has **both** parts: nothing at all for a segment no traffic uses in a year, then a
  **fixed annual cost the moment any traffic uses it**, plus a **variable cost proportional to the
  traffic** on top — an affine function with a positive intercept that is zero at zero traffic and jumps
  to the intercept at any traffic:
  ``f(x) = 0`` for ``x = 0``, ``f(x) = b + a*x`` for ``x > 0``. The reference's reading is the ``a = 0``
  case, the one WS4 had was in effect a per-use charge with no intercept, and this is the shape a road
  budget actually has: a road that is open at all needs work whether or not it is busy, and a busy road
  needs more.
- **A Patchworks-parity mode.** `done` (P12.5, #125), in the smallest form that makes a divergence
  explicit: parity is the default, and what WS4 computes differently is named under the route
  configuration's `divergences`, one entry per quantity, with an unknown entry refused rather than
  ignored. It covers one quantity so far — maintenance — and a second is added the same way rather than
  by building a framework. Quantities that *agree* are not declared at all, because parity is what
  happens when nothing is named. The text below is the record of why, kept as written when it was
  still open. The current
  aim is **verified parity first**: match the reference's semantics, and prove it against its own reports.
  From there WS4 is free to redefine anything it computes — as long as the change is justified,
  documented, and self-consistent — and a mode that *enforces* the reference's readings would let a user
  choose which they get. That mode is the natural home for deliberate divergences like traffic-weighted
  maintenance, and it makes each one explicit rather than implicit.
- **A patch criterion that is a product, evaluated on the treatment's own timeline.** `done` (P13.1,
  #129). A product's curve is a **window over the pre-treatment track's age** (curve 91 is 1.0 on ages
  150–424 and 570–844 — the CC window the treatments table states), the product is produced **in the year
  of its treatment**, and a criterion is its area-weighted mean as a share of the **block**, not of the
  area the treatment covered. `block_criteria` and `block_criteria_series` both compute that as a flow,
  kept as per-year state. The harvested family is compared and agrees in aggregate — area **0.92** of the
  reference's over the horizon, count **1.48** — the same quality and the same shape as the young family,
  so the criterion is accepted and 28 of the reference's 63 patch targets are comparable. Two facts it
  took to get there are recorded in the parity note: the normalisation (the treated area instead of the
  block's put the family at 1.38×, the unmanaged fraction) and the period convention (the reference
  **sums a patch account within a period**, which the harness now does too).
- **The reference's patch `attractor` sub-account.** `open`, blocked on the same export as the patch
  components, and on the same terms: not obtainable from this reference. P12.4 (#124) established from the reference's own 360 values that it is a per-class
  landscape quantity (zero exactly when the class is empty), that it is **not** the class's mean patch
  size, **not** its `size` share (the ratio runs 0.26 to 2.57 cell by cell), and **not** a function of the
  six sub-accounts the export publishes (a log-linear fit leaves a 9% median and a 58% worst residual).
  What it looks like is a lower quantile of the class's patch sizes — within one class it holds a stable
  0.52 to 0.69 of the class's mean patch area, falling to 0.015 in the largest. So WS4 refuses an
  `attractor` sub-account with that reason rather than reporting a `1.0` flag that was not a value, and
  the quantity would become computable from a per-patch distribution — the membership listing above,
  which this reference cannot state (#126).
- **The reference's destination policy for its mill products.** `open`, and narrowed again by P13.2,
  which implemented the mechanism the reference declares and **measured that it does not close the
  gap**. The mechanism is a **delivery target** — `setMinimumAnnual(product.Mill1.Yield.Conif, 80000)`
  in the sample's own `runScenario_test_1.bsh`, which is why its report states 800,000 over a ten-year
  period — declarable in a route config and filled each year from the blocks nearest the destination.
  Imposing it moved the split the **wrong way**: Mill 1's conifer went from 16,617,632 (1.081 of the
  reference's) to 18,613,128 (1.211), because WS4's cost rule *already* sends more than the minimum to
  Mill 1, so a floor only adds. What the reference's numbers actually show is a **search outcome under
  soft bounds**: its achieved Mill 2 in period 1 is 892,306 against a declared maximum of 650,000, with
  no violation reported. So what is left is not a rule to implement but the reference's own trade-off
  between haul cost and its weighted targets, and WS4's least-cost rule is already 91.7% of the way
  there block for block. The mechanism stays — it is the reference's own declaration, and a useful
  capability — with the measurement that it alone does not reproduce the split.
- **Docstring completeness.** `done`. `scripts/doc_audit.py` is the oracle: it checks every public
  function, method, property, class, and module in `ws4` and `scripts/` for the four rules (a docstring
  exists; every parameter is documented and nothing else; a value-returning callable has a `Returns`
  section; a section header is preceded by a blank line). It runs as the `docstrings` gate in
  `scripts/dashboard.py` and as a CI step, with unit tests in `tests/test_doc_audit.py` (P6.45).
- **The TSA23 FT dataset's product table.** `open`. `runtime/ws4/compiled_ft` repeats product rows:
  1,515,465 exact duplicates against 3,431,580 distinct `(track_id, treatment, label, curve_id)` keys,
  up to four rows per key. WS4 records every row once per treated fragment, so
  `product.Treated.managed.FT` reads 4.0000× the treated hectares and the
  `SpeciesProp`/`Yield`/`HarvestedVolume` families 2–4×. The builder drops exact duplicates from P16.2
  onward and the loader warns on a dataset compiled before that; the dataset itself must be recompiled
  to take the fix. Until then `product.FuelTreatmentCost / 20,000` is the clean hectares measure.
  Target: P16.

## P18 follow-ups (not shipped)

- **Model spread-compartment membership.** The source `COMPART` field is a base colour; the per-year
  spread-connectivity compartments the #13 account measures still need a `spread_membership.csv`
  artifact and a map layer. The account itself was independently reproduced on the thesis side.
- **The run's used-road subset.** `--roads` draws the source access network, not the route model's
  opened/used segments. A segment-geometry/use artifact is needed for that overlay.
- **MapLibre and a basemap** when polygon counts or raster layers outgrow the dependency-free SVG shell.
- **A stability stopping criterion** (stop after N iterations without improvement); the player offers
  iterations and time only.
- **Shared embedded assistant.** The local OpenCode assistant is behind `--allow-agent`; a shared
  deployment needs authentication and a deliberate decision about shell/filesystem access.
