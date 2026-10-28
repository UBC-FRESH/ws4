# Change Log

Newest entries last. Each milestone gets a dated entry that matches the roadmap status and the GitHub
issue comments.

## 2026-10-14

- Adopted the UBC-FRESH dev workflow in WS4: added `AGENTS.md`, `ROADMAP.md`, `CHANGE_LOG.md`, and the
  `notes/` tree. Phase 0 (Scope and design) is active on `feature/p0-scope-design`.
- P0.2: wrote the problem statement and scope in `notes/design/ws4-scope.md`.
- P0.3: recorded six architecture decisions in `notes/adr/0001` to `notes/adr/0006`.
- P0.4: wrote the architecture design in `notes/design/ws4-architecture.md`.
- P0.6: neutralized third-party naming in the skeleton. Renamed the XML recipe module to
  `ws4/io/forest_model_xml.py`, and reworded the CLI help, README, and docstrings to describe an
  "XML recipe" and a "launch control file". A repository-wide check for the old vocabulary is clean.
- P0.5: installed the UBC-FRESH dev workflow tooling. Added `scripts/check_workflow.py` and
  `scripts/dashboard.py`, the docs skeleton, the framework tests, the CI workflows, the issue
  templates, `requirements-dev.txt`, `.pre-commit-config.yaml`, and the recommended `LICENSE`,
  `CODE_OF_CONDUCT.md`, and `CITATION.cff`. Merged the tool configuration into `pyproject.toml` and
  fixed the skeleton to pass lint, format, and types.
  Dashboard result: `python scripts/dashboard.py` reports `OVERALL: GREEN` on all six gates (lint,
  format, types, tests, validator, docs).
- Opened the Phase 0 parent issue #1 and child issues #2 to #7. Closed the child issues with closeout
  comments, and set the phase to `pr-open`.
- P0.7: recorded the optimization and execution architecture in
  `notes/design/ws4-optimization-stack.md`, with ADR 0007 (layered, pluggable optimization stack),
  ADR 0008 (Python first, C++ kernels behind a stable API), ADR 0009 (parallel and GPU execution), and
  ADR 0010 (telemetry-driven tuning and the meta-meta-heuristic portfolio). Updated the scope and the
  architecture note, and added the P2 build tasks for the solver core, the execution substrate, and the
  math-heuristic layer.
- Queued the Phase 0 close-out: pull request #8 (`feature/p0-scope-design` into `main`) and the report
  `notes/reports/p0-closeout.md`. Status: awaiting maintainer approval.
- Completed Phase 0: squash-merged pull request #8 as `97330a8`, deleted `feature/p0-scope-design`, and
  closed parent issue #1.
- Launched Phase 1 (Contracts and prototype) on `feature/p1-contracts-prototype`, parent issue #10, with
  tasks P1.1 (compiled-dataset schema and manifest) and P1.2 (end-to-end prototype).
- P1.1: defined the compiled-dataset schema and manifest. Added `ws4/model/schema.py` (tables, manifest,
  validator), `docs/reference/compiled-dataset.rst`, a `ws4 validate` implementation, `tests/test_schema.py`,
  and the package `__init__.py` files plus the `ws4.build.compiler` stub. Added `pandas-stubs` to the dev
  requirements. Dashboard result: `python scripts/dashboard.py` reports `OVERALL: GREEN`.
- P1.2: built the end-to-end prototype. Added `examples/synthetic/` (recipe, fragments, notes), a real
  `ws4 build` compiler that writes the matrix and manifest, a real `ws4 simulate` that replays a schedule
  and writes `account_values.csv`, `ws4/sim/curve.py`, and `tests/test_prototype.py` (build, validate,
  grow, and treat). Dashboard result: `python scripts/dashboard.py` reports `OVERALL: GREEN`.
- P1.3: adopted the established ForestModelXML recipe format and recorded the matrix builder and legacy
  dataset ingestion in `notes/design/ws4-matrix-builder-and-interop.md`, with ADR 0011 (adopt the format
  and support legacy datasets) and ADR 0012 (two construction paths: file-based and programmatic). Updated
  the scope, the architecture note, and the P2 tasks.
- Queued the Phase 1 close-out: pull request #14 (`feature/p1-contracts-prototype` into `main`) and the
  report `notes/reports/p1-closeout.md`. Status: awaiting maintainer approval.
- P1 fix: the CI jobs now install the package (`python -m pip install -e .`) before the gates, because
  mypy and pytest need the runtime dependencies (pydantic, pandas, numpy, pyarrow). Added
  `[tool.setuptools.packages.find]` so the package builds. The pre-commit parity job is green again.
- P1 fix: the `.gitignore` rule `build/` also ignored the `ws4/build/` package, so the compiler was
  never committed. Narrowed the rule to `/build/` and committed `ws4/build/__init__.py` and
  `ws4/build/compiler.py`. This is why CI could not resolve `ws4.build.compiler`.
- Completed Phase 1: squash-merged pull request #14 as `a3d182a`, deleted `feature/p1-contracts-prototype`,
  and closed parent issue #10.
- Launched Phase 2 (Build) on `feature/p2-build`, parent issue #15, with tasks P2.1 to P2.9 (#16 to #24).
- P2.1 (in progress): replaced the prototype's minimal recipe parser with a ForestModelXML parser and
  matrix builder, and added legacy matrix ingestion. The parser handles the real MKRF recipe
  (`baseMKRF.xml`: 1057 curves, 11 selects, CC and CT treatments, 14 features, 14 products) and the
  select statement operators `eq`, `ne`, `lt`, `le`, `gt`, `ge`, `in`, with opaque terms for function
  calls. Added `ws4 ingest`, `tests/test_forest_model_xml.py`, and `tests/test_legacy.py`, and a
  `docs/reference/forestmodelxml.rst` page that records the known gaps (full expression evaluation,
  expression-sourced curves, `%`-token labels, succession/retention, shapefile input). Dashboard result:
  `python scripts/dashboard.py` reports `OVERALL: GREEN`.
- Recorded the Model II formulation in `notes/design/ws4-matrix-builder-and-interop.md` (section 4) and
  `docs/reference/forestmodelxml.rst`: state variables define a stratum, a track is a unique trajectory
  over time between two treatments, and a treatment resets state variables, which switches the block to
  the target stratum's track. This is the expansion engine the matrix builder needs, and it explains the
  reference matrix's 7048 tracks and its per-portion block rows.
- P2.1: implemented the Model II expansion engine (`ws4/build/expansion.py`). The builder now enumerates
  the reachable strata (inventory plus treatment transitions, to a fixed point), expands each stratum
  into a track, treats a stratum as governed by every matching select (so features, products, and
  treatments accumulate), and emits one block row per portion. On the reference recipe and fragments this
  yields 1399 strata and 2024 treatment rows (from 0). Added `tests/test_expansion.py`. Dashboard result:
  `python scripts/dashboard.py` reports `OVERALL: GREEN`.
- P2.1: completed the Model II expansion against a reference matrix. Added field-reference and
  concatenation transition resolution (`au = auf`, `'thn_'+au`) and `<retention>` splits (the retained
  fraction moves to the assigned state). Against a real 218-fragment instance, the builder now matches
  the reference exactly on tracks (351), strata (351), treatments (263), and blocks (399).
- P2.1: canonicalized numeric state values (an integral float renders without a decimal part) so a
  numeric column matches an integer literal in a select. With that fix, the builder matches every tested
  reference matrix exactly: the k3z intensive variants (732/732/963/427 and 553/553/605/427) and a
  421,945-fragment instance (tsa29: tracks 524, strata 524, treatments 210). Added the backlog note
  `notes/backlog.md` as the consolidated gap list.
- P2.1: added a bounded select-expression evaluator (`ws4/io/expressions.py`): comparisons, booleans,
  parentheses, and the functions `startswith`, `endswith`, `substring`, `int`, `Number`, `length`, and
  `if`, with a fallback to the term matcher. The k3z reference matrices still match exactly, and the
  MKRF PoC CT eligibility now evaluates (`not startswith(au,'t')`).
- P2.1: the builder now matches the k3z reference exactly on **features and products** as well. A select
  with a `treatment eq 'X'` context contributes products tagged `X` to the stratum matching its other
  terms (it is not a stratum dimension), and accounts are the union of feature and product labels grouped
  by management state. Accounts are close but not exact (k3z pct_light 1507 vs 1460; the reference
  excludes zero-signal families, recorded in the backlog).
- P2.2: implemented the annual simulator over the compiled contract. A scheduled treatment applies only
  where the fragment's track offers it (the Model II operability rule) and moves the fragment to its
  `new_track`. Applying a treatment records its product yield (area times the product curve at the
  pre-treatment offset) to `product_values.csv`. Added `tests/test_simulator.py` (deterministic replay;
  an unoffered treatment is a no-op; a treatment records its product yield).
- P2.2: implemented patch metrics over the block topology (`ws4/patch/metrics.py`): connected patches,
  size classes, and mean size. The simulator writes `patch_metrics.csv` when given a topology. Added
  `tests/test_patch.py` and a simulator patch-metric test.
- P2.3: implemented the weighted-goal objective (`ws4/opt/objective.py`, targets from YAML), a
  neighbourhood-operator registry (`ws4/opt/operators.py`: toggle, shift, swap), and a seeded
  simulated-annealing optimizer (`ws4/opt/engine.py`) that evaluates candidates through the simulator.
  Added `tests/test_optimizer.py`; `pyyaml` and `types-PyYAML` added to the dependencies.
- P2.3: extracted three metaheuristics into `ws4/opt/solvers.py` — simulated annealing, tabu search, and
  iterated local search — selected by `OptimizeConfig.metaheuristic` over the same operator registry and
  objective. `tests/test_optimizer.py` runs all three and checks each lowers the penalty.
- P2.4: added multi-start to the optimizer (`OptimizeConfig.starts`); each start uses its own seed and the
  best incumbent wins. A test asserts more starts is no worse than fewer.
- P2.7: implemented the road network subsystem (`ws4/roads/network.py`): load the four tables, build the
  segment graph, and route by shortest length or cost, with nearest-destination lookup. Added
  `tests/test_roads.py`.
- P2.7: routed the simulator's product flows. When given a road network, the simulator sends each
  produced product to the block's single nearest destination (exclusive by construction) and writes
  `route_values.csv` (volume, route length, and cost). Added a routing test.
- P2.9: implemented the programmatic model API (`ws4/model/api.py`). A `Model` holds one DataFrame per
  matrix table, with `append` and `replace`; `from_dataset` loads and `write` saves, round-tripping a
  dataset. Added `tests/test_model_api.py`.
- P2.4: defined the solver-core boundary (`ws4/opt/core.py`: a `Problem` adapter with an evaluator,
  candidate moves, and an operator registry) and refactored the solvers to take it. Added run telemetry
  (`ws4/opt/telemetry.py`: a JSONL header and one step record per iteration); the optimizer writes
  `telemetry.jsonl`. Added telemetry tests.
- P2.5: added parallel multi-start (`OptimizeConfig.workers`). Starts run across a process pool, one
  seeded start per worker, and the best incumbent wins; the serial path is unchanged. Added a parallel
  test.
- P2.6: added the destroy-repair large-neighbourhood operator (`lns`, in the default registry) and warm
  starts (`OptimizeConfig.warm_start` seeds the search from each block's first candidate). Added tests.
- P2.6: implemented a mixed-integer penalty bound (`ws4/opt/mip.py`). Each block's no-treatment value and
  each option's delta are measured with the block's fragments isolated; an option-selection MILP (HiGHS
  via `scipy.optimize.milp`) minimizes the linearized weighted penalty for a valid lower bound and a
  candidate schedule. Added `tests/test_mip.py`.
- P2.6: wired the MIP bound into the optimizer (`OptimizeConfig.mip_bound`); the run summary records the
  bound, the gap (incumbent minus bound), and the bound status. Added a test asserting a non-negative gap.
- P2.1: resolved `<expression>`-sourced attribute curves. The select-expression evaluator gained string
  concatenation, arithmetic, and the `curveId`, `attribute`, and `lastindexof` functions, and the builder
  evaluates an attribute's expression per stratum to a curve name. On the MKRF PoC the expression-sourced
  features and products now resolve. Added an expansion test.
- P2.1: expanded `%f` (feature/product) and `%m` (managed/unmanaged) label tokens and evaluated
  expression labels (`'%f.area.%m.state.'+if(...)`). The evaluator now short-circuits `and`/`or` and
  treats a non-numeric `int`/`Number` operand as zero, so labels resolve on every stratum. Added a test.
- P2.1: expanded the remaining label tokens (`%au`, `%s`) and implemented the `factor` expression. A
  factor scales the attribute's curve into a derived curve (reused per base curve and factor), so a
  scaled feature or product references its own curve. Added a factor test.
- P2.1: added shapefile input (`ws4/io/fragments.py`): the builder reads a shapefile, GeoJSON,
  GeoPackage, CSV, or Parquet fragment inventory, importing the geo dependency lazily. CI installs the
  `geo` extra, and `tests/test_fragments.py` covers it.
- P2.1: evaluated the ``<input>`` block/area/age expressions against the fragment row, so a raw inventory
  with `RES_KEY`/`Shape_Area`/`AGE_2020` columns works without pre-renaming. Added an expansion test.
- Synced the UBC-FRESH dev workflow tooling to its latest release (P1-P4): updated
  `scripts/check_workflow.py` and the CI action versions and runners (`ubuntu-24.04`, `checkout@v5`,
  `setup-python@v6`, `upload-artifact@v6`, and the Pages actions), keeping the package install step.
- P2.8: implemented accounts and reporting (`ws4/report.py`): an account summary, a ratio account, and a
  target-status table; `ws4 report` is a CLI command, and the optimizer writes a report at the end of a
  run. Added `tests/test_report.py`.
- P2.1: corrected the account semantics. The builder now writes a `protoaccounts` table — a summary
  account for every attribute, grouped by the managed state of the producing selects (`_MANAGED_`,
  `_UNMANAGED_`, `_ALL_`) — matching the reference `protoaccounts.csv` exactly on all nine core k3z
  variants (pct_light/heavy/moderate, intensive_light/moderate/heavy/standstructure, ctfert_l15h5/l20h0).
  A user's curated `accounts` table is preserved across rebuilds. Added the `sum` scale column and tests.
  The `overlay_*` variants are a modelling convention for one instance family, not a format feature, so
  they are out of scope.
- P2 close-out: queued pull request #25 (`feature/p2-build` into `main`) and wrote
  `notes/reports/p2-closeout.md`. `ROADMAP.md` marks P2 `pr-open`; five items are deferred and tracked
  in `notes/backlog.md`. `python scripts/dashboard.py`: `OVERALL: GREEN`.
- P2 close-out fix: `ws4/opt/mip.py` imported `scipy` at module load, so a plain install could not import
  the optimizer and CI (which installed only `.[geo]` plus the dev requirements) failed on `f22cd6a`. The
  import is now lazy with a clear error, `scipy` is declared in the `opt` extra and the dev requirements,
  and `tests/test_mip.py` skips when it is absent.
- P2 close-out carried out: pull request #25 squash-merged as `27b6915`, branch `feature/p2-build`
  deleted, and parent issue #15 closed. P2 is `complete` in `ROADMAP.md`. Launched P3 (Verify): parent
  issue #26, branch `feature/p3-verify`, task P3.1 (#27).
- P3: made the repository public and enabled GitHub Pages (`gh api -X PATCH repos/UBC-FRESH/ws4
  -f visibility=public`, then `gh api -X POST repos/UBC-FRESH/ws4/pages -f build_type=workflow`), so the
  `Docs` deploy job can publish to `https://ubc-fresh.github.io/ws4/`. Pages was unavailable while the
  repository was private under the Free plan.
- P3.1: ran the acceptance checks and recorded the evidence in `notes/acceptance.md`. Added a repeatable
  `scripts/acceptance.py` (builder-vs-reference, prototype, optimizer, roads, and api checks). Result:
  the builder matches the reference compiled matrices on all nine core variants; the C5 sample ingests
  with 0 validation problems and simulates 30 years in 15.5 s; the optimizer meets its target; routing
  and the programmatic model round-trip pass. `python -m pytest`: 218 passed, 94.78 percent branch
  coverage. `python scripts/dashboard.py`: `OVERALL: GREEN`.
- P3: reviewed and expanded every remaining phase plan. Verify now has seven tasks (#27 to #33):
  acceptance checks (done), determinism and reproducibility, correctness (reference regression and
  invariants), the spatial constraints, scale and performance, packaging and docs from a clean checkout,
  and the deferred-item triage and verification report. Release and deploy now has six tasks
  (release preparation, notes, artifacts, docs, tagging, and post-release verification). Operate and
  maintain now has six tasks (review cadence, triage, dependency and security maintenance, planning
  upkeep, release cadence, and a maintainer guide).
- P3.2: verified determinism and reproducibility. The simulator is deterministic; the same seed
  reproduces the same objective and schedule; a parallel multi-start run matches the serial run; a warm
  start is deterministic (and intentionally differs from a cold start, so the criterion was corrected);
  and a run directory now records the dataset manifest (`dataset_reference` in `ws4/model/schema.py`,
  used by the optimizer's `summary.json` and the simulator's `dataset.json`). `python -m pytest`: 224
  passed, 94.78 percent branch coverage. `python scripts/dashboard.py`: `OVERALL: GREEN`.
- P3.3: verified correctness. Added a self-contained matrix regression fixture
  (`tests/fixtures/matrix/`, with committed `expected/` tables) and `tests/test_matrix_regression.py`;
  property tests for the Model II expansion invariants (every stratum has a track; every treatment
  connects to a real target track or 0; retention splits conserve area, with a hypothesis test over
  random areas); strengthened `validate_dataset` to check strata, treatments, features, and products
  against real tracks and curves (with tests per new finding); and a test that no random schedule has a
  penalty below the MIP bound. The builder still matches the reference on all nine core variants.
  `python -m pytest`: 240 passed, 94.78 percent branch coverage.
- P3.4: verified the spatial subsystem. Patch metrics now include the largest opening per year
  (`max_patch_area`), and they match an independent hand calculation on a small topology; the simulator
  reports the largest opening in `patch_metrics.csv`. Gap found: no code enforces adjacency, a maximum
  opening size, or green-up, and the optimizer's objective has no spatial term. Recorded as a release
  gap in `notes/backlog.md`; the scope lists these constraints as in scope through the first release, so
  they must be closed before P4.
- P3.8: implemented and enforced the spatial constraints. `ws4/patch/constraints.py` reports the largest
  opening per year, opening violations, green-up violations, and a combined penalty; the simulator writes
  `spatial_violations.csv`; and the optimizer adds a weighted spatial penalty to its objective, disabled
  by the explicit `allow_spatial_override`. The CLI exposes `--topology`, `--max-opening-ha`,
  `--min-green-up-years`, and `--spatial-override`. The P3.4 gap is closed. `python -m pytest`: 254
  passed, 94.78 percent branch coverage. `python scripts/dashboard.py`: `OVERALL: GREEN`.
- P3.5: verified scale and performance (`notes/performance.md`, `scripts/benchmark.py`). Profiling found
  two hot paths and both were fixed: the builder re-parsed each select expression per fragment (now
  cached by statement; build of 100 038 fragments 3.79 s to 1.66 s), and `account_values` used a per-curve
  `pandas` `.loc` setitem (now a positional numpy assignment; the C5 30-year simulate 15.5 s to 4.2 s).
  The synthetic build is linear in the fragment count, curve evaluation is vectorized per curve, and the
  block-aggregation cost is not the hot path, so the cached incremental aggregate is deferred.
  `python -m pytest`: 264 passed, 94.28 percent branch coverage. `python scripts/dashboard.py`:
  `OVERALL: GREEN`.
- P3.6: verified packaging and docs from a clean checkout (`notes/packaging.md`). A fresh virtual
  environment installs `ws4 0.0.1`; the command line runs end to end (`ws4 build`, `simulate`, `report`,
  `validate`) on the synthetic fixture; the docs build with warnings as errors; and the published site
  returns HTTP 200.
- P3.7: triaged the deferred items and wrote the verification report. Every `notes/backlog.md` item now
  names a target phase (`P4`, `P5`, `post-release`, or a condition), the roadmap's P2 deferred list was
  reconciled with the backlog, and `notes/reports/p3-verify.md` records the findings and recommends
  proceeding to P4. No open item is release-blocking.
- P3 close-out: queued pull request #35 (`feature/p3-verify` into `main`) and wrote
  `notes/reports/p3-closeout.md`. `ROADMAP.md` marks P3 `pr-open`. `python scripts/dashboard.py`:
  `OVERALL: GREEN`.
- P3 close-out carried out: pull request #35 squash-merged as `a8dc018`, branch `feature/p3-verify`
  deleted, and parent issue #26 closed. P3 is `complete` in `ROADMAP.md`. Launched P4 (Release and
  deploy): parent issue #36, branch `feature/p4-release`, tasks P4.1 to P4.6 (#37 to #42).

## 2026-10-15

- P4.1: prepared the release. Bumped the version to `0.1.0` (`pyproject.toml` and `ws4/__init__.py`),
  added classifiers, keywords, and project URLs, and set the citation version and release date.
  Confirmed the Apache-2.0 license, and that `CHANGE_LOG.md` is current through P3. Removed the empty
  `debug.ipynb` skeleton stub. The installed metadata reports version `0.1.0` with the four project URLs.
- P4.2: wrote `RELEASE_NOTES.md` for the first release: what is included, install and quick start, the
  performance figures, the verification summary, the known gaps (the blocked MKRF model and the future
  work in `notes/backlog.md`), and the out-of-scope items. Also normalized the acronym `MKRf` to `MKRF`
  across the repository (8 files).
- Materialized the canonical MKRF artifacts for the downstream check: `xml/forestmodel.xml` and
  `tracks/{curves,features,products}.csv` were fetched from the public `arbutus-s3` bucket by their
  chunked keys and `git annex reinject`ed, after all four SHA-256 values matched the producer's. The
  remaining blockers are recorded in `notes/backlog.md`: the producer's git-annex branch was not pushed
  to `origin`, and the recipe's defines use `lookupTable(...)`, which the expression evaluator does not
  implement.
- Fixed the builder for the canonical MKRF recipe and reproduced its core matrix exactly: **tracks
  7048/7048, strata 7048/7048, treatments 10014/10014, blocks 3183/3183**. Four fixes: `lookupTable` in
  the expression evaluator; expression-based `<define column>` values evaluated against the fragment
  row; a literal retention factor (previously read as a column name and treated as zero, which had
  dropped every unmanaged stratum); and label/product expressions without `%` tokens, with context-less
  product selects tagged per treatment (products 274872 → 390546). The nine k3z core variants still
  match exactly. Remaining: five labels need `operable(...)` and the runtime curve bank
  (features 97522/104311, products 390546/420588). `python -m pytest`: 270 passed.
- P4 fix (maintainer request): the canonical MKRF model now builds **exactly**. The last five labels
  closed the gap: a `<features>` element nested inside `<retention>` is parsed (`retention_features`)
  and attaches to the retained stratum, so `feature.area.retention.total` is produced; the evaluator
  gained `operable(x)` and a real `attribute('label')` lookup against the labels already emitted for a
  stratum, so `feature.yield.managed.merch.total` resolves to the base yield curve; a curve reference
  (`CurveRef`) survives scaling and offsetting arithmetic, so `product.Cost_Total`/`NetRevenue` resolve
  instead of concatenating to a bogus name or raising; and an expression that evaluates to a number
  becomes a generated constant curve, so `product.Cost_Silviculture` is produced (per treatment
  context). Result: tracks 7048/7048, strata 7048/7048, treatments 10014/10014, blocks 3183/3183,
  features 104311/104311, products 420588/420588, protoaccounts 91/91 (row counts and label sets;
  `scripts/acceptance.py`). Updated `docs/reference/forestmodelxml.rst`. Dashboard result:
  `python scripts/dashboard.py` reports `OVERALL: GREEN`. `python -m pytest`: 278 passed.
- P4.3 (in progress): built and verified the release artifacts. From a clean checkout,
  `python -m build` produced `dist/ws4-0.1.0.tar.gz` and `dist/ws4-0.1.0-py3-none-any.whl`. The wheel
  installs into a fresh virtual environment (Python 3.12) and its `ws4` console script runs the full
  path end to end: `ws4 build` → `ws4 validate` → `ws4 simulate` → `ws4 report` → `ws4 optimize` all
  succeed on the synthetic example, the optimizer meeting its target with an objective of 0. The wheel
  contains only `ws4/` and the dist-info. Added `MANIFEST.in` so the sdist carries the package and not
  the tests or the notes. Also refreshed `RELEASE_NOTES.md`: the MKRF canonical model is now reported as
  reproduced, and the test count is 278.
- P4.4 (partial): added the subsystem documentation pages assigned to P4 — `docs/reference/simulator.rst`
  (the annual-step engine, its schedule, and its run outputs), `optimizer.rst` (the objective, the
  operator registry, the metaheuristics, and the MIP bound), `spatial.rst` (the block topology, patch
  metrics, and the opening and green-up rules), and `roads.rst` (the network tables, shortest-path
  routing, and the route outputs). Wired them into the docs toctree and the `docs/llms.txt` index. The
  remaining P4.4 subtasks (confirm the `Docs` workflow deploys from `main`, and verify the published
  site) depend on the phase merging to `main`. Dashboard result: `python scripts/dashboard.py` reports
  `OVERALL: GREEN`.
- P4 fix (maintainer request): the C5 route model and patch accounts. **Roads/route/mill/product.**
  A destination is now identified by its account name and several destinations may share a vertex
  (before, MILL1 and MILL3 at the same node collapsed to one). Added a route model
  (`ws4/roads/accounts.py`) with product eligibility, an exclusive destination choice per product per
  block, and an optional unutilized (surplus) account; a route cost ledger that charges haul cost by
  volume, build cost once (first period a segment is used), and maintenance cost each period used; and
  the route outputs `route_values.csv`, `network_table.csv`, `route_table.<destination>.csv`, and
  `route_cost_report.csv` (the established columns). Shortest paths are cached, so the C5 run is fast.
  **Patch accounts.** Added `ws4/patch/accounts.py`: the patch criteria attribute with a threshold,
  the size classes, and the `area`, `size`, `shape`, `frequency`, and `attractor` sub-accounts; the
  criteria value per block is derived from a feature curve (`Simulator.block_criteria`). The topology
  loader accepts the established `BLOCK1,BLOCK2,DISTANCE,LENGTH` columns with the `-9999` sentinel.
  Verified on the C5 sample end to end: ingest (0 validation problems), 3 destinations, a route cost
  report with haul/build/maintain, and a per-period `patch_accounts.csv`. Also documented the road and
  patch accounts and updated `notes/backlog.md`. Dashboard result: `python scripts/dashboard.py`
  reports `OVERALL: GREEN`. `python -m pytest`: 291 passed.
- P4 fix (maintainer request): closed the remaining route-account gaps. Added **route accounts**
  (`RouteAccount`, matching `addRouteHaulAccount` and friends) that sum a destination's haul, build,
  maintenance, or volume into a named account, and **duplicate accounts** (`DuplicateAccount`,
  matching `duplicateAccount`) that copy an account into another with a factor.
  `resolve_account_values` combines the simulated values, the route account values, and the
  duplicates. A **route configuration** YAML (`load_route_config`) names the route tables,
  eligibility, unutilized account, route accounts, and duplicate accounts. The **optimizer** now
  loads the route config (`OptimizeConfig.route_config_path` / `--route-config`), evaluates its
  objective with the route model, and resolves the route and duplicate accounts before scoring, so
  targets can be set on accounts such as `route.Total.haul`; the CLI `ws4 simulate` also accepts
  `--route-config`. Verified on C5: the route accounts resolve (`route.Total.haul` = MILL1 + MILL2
  haul; `product.Harvested` = the mill volumes), and a single-iteration optimize with a
  `route.Total.haul` target scores and writes the route tables. Note: routing in the optimizer's
  inner loop is the current cost (a C5 single-iteration run is ~13 minutes); incremental routing is
  recorded in `notes/backlog.md`. Dashboard result: `python scripts/dashboard.py` reports
  `OVERALL: GREEN`. `python -m pytest`: 296 passed.
- P4 fix (maintainer request): closed the spatial function gaps — **core-area rules** and **edge
  contrast**. `core_area` removes a buffer strip around a patch perimeter (from the perimeter and
  area); `core_area_violations`/`core_area_penalty` report and penalize patches whose core is below a
  minimum. `edge_contrast` sums the shared boundary where one side matches the first attribute and the
  other matches the second, weighted by the shared edge length; `ws4/patch/edge.py` loads edge elements
  and produces a per-period edge account. The simulator accepts `core_buffer_m`, `min_core_area_ha`,
  and `edge_elements`, writes core-area rows into `spatial_violations.csv` and `edge_metrics.csv`, and
  adds the edge accounts to `account_values.csv`; the optimizer (`--core-buffer-m`,
  `--min-core-area-ha`, `--edge-elements`) adds the core-area penalty and can target the edge accounts.
  Verified on C5: 167 core-area violations at a 500 ha minimum / 50 m buffer, and
  `feature.Edge.OldYoung` = 700748 m of old/young contrast edge. Dashboard result:
  `python scripts/dashboard.py` reports `OVERALL: GREEN`. `python -m pytest`: 300 passed.
- P4 planning (maintainer request): recorded the post-release performance and scalability plan in
  `notes/design/ws4-performance.md`. It profiles the spatial+route path on the C5 sample, maps the
  bottlenecks (route reconstruction rebuilt per call, row-wise `apply_treatments`, per-year criteria
  merges, double replay, no incrementality, single-threaded inner loop), and lays out the strategic,
  tactical, and operational plan: precompute a spatial index, incremental (delta) objective
  evaluation, a vectorized array simulator, an island/parallel substrate, and native kernels behind
  the Python API. Targets: C5 30-year simulate <1 s, one optimizer objective evaluation <50 ms,
  near-linear scaling to 32+ cores. The implementation is deliberately deferred until after the phase
  4 initial release ("functionally complete but slow"); the release notes and `notes/performance.md`
  record the current limits. Also indexed the plan in `notes/README.md` and the roadmap.
- Queued the Phase 4 close-out: pull request #43 (`feature/p4-release` into `main`) and the report
  `notes/reports/p4-closeout.md`. The report recommends the squash merge, the `v0.1.0` tag and release
  (P4.5), the docs publish and verification (P4.4), the post-publish verification (P4.6), closing parent
  issue #36, and launching P5, with the exact commands. Set P4 to `pr-open` in `ROADMAP.md`. Status:
  awaiting maintainer approval. CI on the evidence head `4516345` is green.
- Completed Phase 4 (Release and deploy): squash-merged pull request #43 as `d8ecd72`, deleted the
  branch `feature/p4-release`, and closed parent issue #36. Created and pushed the annotated tag
  `v0.1.0`, and published the GitHub release `v0.1.0` with the sdist (`ws4-0.1.0.tar.gz`) and the wheel
  (`ws4-0.1.0-py3-none-any.whl`), built from a clean checkout of the tag. Verified the published docs
  site (`https://ubc-fresh.github.io/ws4/`, the Docs workflow run `38785009892` on `main`) and the
  published artifact (P4.6): a fresh virtual environment installed the released wheel, and the `ws4`
  command ran build, validate, simulate, report, and optimize end to end; the simulator was
  reproducible (identical `account_values.csv`) and the optimizer reproduced its objective for the same
  seed. Fixed a stale roads docs line (`ed4b530`).
- Launched Phase 5 (Operate and maintain) on `feature/p5-operate`, parent issue #44, with tasks P5.1 to
  P5.6 (#45 to #50): a review cadence, issue triage, dependency maintenance, a
  roadmap/backlog/changelog sync, a release and patch policy, and a maintainer and handover guide. The
  performance build phase follows P5 (`notes/design/ws4-performance.md`).
- P5.1: set the review cadence (monthly, on the first working day, plus out-of-cadence triggers for a
  security advisory, a broken release, or a scope change) and recorded the first review in
  `notes/review-cadence.md`. Dashboard result: `python scripts/dashboard.py` reports `OVERALL: GREEN`.
- P5.2: stood up issue triage. Added type labels (`performance`, `security`, `chore`), priority labels
  (`priority: high|medium|low`), and area labels (`area: builder|simulator|optimizer|spatial|roads|
  docs|performance|tooling`); added a pull request template; and recorded the label scheme, routing
  rules, and triage cadence in `notes/triage.md`.
- P5.3: dependency and security maintenance. Added `.github/dependabot.yml` (weekly pip and
  github-actions updates) and recorded the review cadence and the out-of-cadence advisory policy in
  `notes/dependencies.md`.
- P5.4: recorded the roadmap/backlog/changelog sync checklist and the first sync in
  `notes/sync-checklist.md`, and linked it from the review cadence.
- P5.5: recorded the version scheme, release cadence, patch policy, and artifact hosting in
  `notes/release-policy.md`.
- P5.6: wrote the maintainer and handover guide in `notes/handover.md` (repository map, workflow,
  gates, releases, environment, and the next effort). Dashboard result: `python scripts/dashboard.py`
  reports `OVERALL: GREEN`. `python -m pytest`: 300 passed.
- Queued the Phase 5 close-out: pull request #51 (`feature/p5-operate` into `main`) and the report
  `notes/reports/p5-closeout.md`. The report recommends the squash merge, closing parent issue #44,
  setting P5 to `complete`, and launching the performance and scalability build (P6, the plan in
  `notes/design/ws4-performance.md`) with its WP0 to WP7 work packages. It names one settings change
  (Dependabot security updates). Status: awaiting maintainer approval. CI on the evidence head
  `880c14a` is green.
- Completed Phase 5 (Operate and maintain): squash-merged pull request #51 as `a8cb148`, deleted the
  branch `feature/p5-operate`, and closed parent issue #44. Enabled Dependabot security updates
  (version-update pull requests are already open).
- Launched Phase 6 (Performance and scalability) on `feature/p6-performance`, parent issue #60, with
  work packages P6.0 to P6.7 (#61 to #68) from `notes/design/ws4-performance.md`.
- P6.0: extended `scripts/benchmark.py` with a `c5` spatial+route scenario (`--scenario c5
  --sample-dir ... --route-blocks ... --spatial-years ...`) that times ingest, base simulate, edge
  contrast, routing, patch accounts, and one optimizer objective evaluation, plus `--profile`. Recorded
  the reproducible baseline in `notes/performance.md`: ingest 0.24 s, base simulate (3 y) 0.88 s, edge
  contrast 3.6 s, routing (3 y, 300 blocks) 65.4 s, patch accounts 2.2 s, one objective evaluation
  1.3 s, peak memory 2.8 GiB. Dashboard result: `python scripts/dashboard.py` reports `OVERALL: GREEN`.
- P6.1: route and simulation quick wins. The route-network indexes are built once; the treatment,
  product, and fragment lookups are precomputed; `apply_treatments` is vectorized (no pandas
  `iterrows`); and routing uses per-destination shortest paths (the graph is undirected, so one
  Dijkstra per destination serves every block). C5 `simulate` + routing (3 years, 300 blocks) fell
  from 65.4 s to **4.5 s**, and peak memory from 2.8 GiB to **338 MiB**. The single-replay subtask is
  deferred to WP3. Dashboard result: `python scripts/dashboard.py` reports `OVERALL: GREEN`.
- P6.2: vectorized simulator core. `account_values` now uses a precomputed fragment-to-feature join
  (flat arrays of fragment position, curve id, and label code, rebuilt only when a track changes) with
  per-curve `numpy.interp`, instead of a per-year pandas merge and groupby. C5 `simulate` base fell from
  3.76 s to **0.41 s** over 30 years (target under 1 s met). The benchmark now times simulator
  construction separately. Dashboard result: `python scripts/dashboard.py` reports `OVERALL: GREEN`.
- P6.3: spatial precompute and incremental metrics. `block_criteria` uses a precomputed per-label join
  with `numpy.interp` and `np.bincount` (no pandas merge/groupby per label per year), and the patch
  perimeter is a single pass over the edges instead of a per-patch scan. C5 edge contrast fell from
  3.0 s to **0.31 s** (3 y; 0.070 s/yr) and patch accounts from 1.9 s to **0.25 s** (1 y; 0.066 s/yr),
  both under the 0.2 s-per-year target. Full-history incrementality and the single replay in `run` move
  to WP4. Dashboard result: `python scripts/dashboard.py` reports `OVERALL: GREEN`.
- P6.4 (in progress): incremental objective evaluation. First, the removal of per-evaluation waste:
  the optimizer reuses one `Simulator` (`Simulator.reset` restores tracks/offsets instead of
  reconstructing); `apply_treatments` evaluates curves from the precomputed per-curve arrays (the old
  `curve_value` masked the whole 130 423-row curves frame per product); the route model memoizes the
  destination choice per (block, product); the route ledger has a summary mode (`collect=False`) that
  keeps only the per-destination totals the objective needs; and the fragment-to-feature join is
  rebuilt with a vectorized numpy expansion. C5 warm objective evaluation fell from ~3.8 s to ~0.28 s
  (300-block schedule, 10 years) and ~1.3 s to ~0.23 s (empty). The delta evaluation (base plus
  per-block contributions) is the next step. Dashboard result: `python scripts/dashboard.py` reports
  `OVERALL: GREEN`.
- P6.4: incremental objective evaluation. Feature account values are additive over blocks, so the
  objective is the empty-schedule base plus a per-block delta (base and deltas cached, lazily per
  assignment); edge contrast and route accounts fall back to the full simulation (not additive over
  blocks). Parity with the full simulation holds to floating-point tolerance. C5 10-year warm
  evaluation: ~1.29 s to 0.23 s (empty) and ~3.8 s to **6.7 ms** (300-block schedule), meeting the
  under-50 ms target. Dashboard result: `python scripts/dashboard.py` reports `OVERALL: GREEN`.
- P6.5: solvers at scale. Added an island model (`OptimizeConfig.islands` / `episodes`, `--islands` /
  `--episodes`): islands run as parallel processes and, after each episode, the global best schedule is
  migrated into every island as the next episode's starting point. Deterministic for a given seed
  (tested), and no worse than a single start. NUMA-aware placement and batched/candidate-level parallel
  move evaluation remain as future refinements. Dashboard result: `python scripts/dashboard.py` reports
  `OVERALL: GREEN`.
- P6.7: guardrails. Added `tests/test_performance.py` (the incremental objective must be strictly faster
  than a full simulation and must match it on random schedules; the simulator is deterministic), and a
  user-facing `docs/reference/performance.rst` page with the measured figures, the incremental
  objective, and the reproduce steps. Dashboard result: `python scripts/dashboard.py` reports
  `OVERALL: GREEN`.
- P6.6 (native kernels) is deferred after post-P6 profiling found no loop with a large kernel speedup;
  numba is not installed in CI. Recorded in the roadmap's "Deferred from P6" list, `notes/backlog.md`,
  and `notes/design/ws4-performance.md`, with a trigger to revisit. Issue #67 closed as not planned.
- P6.6 investigation (thread-level parallelism): measured on the C5 numeric core; threads make the
  curve-evaluation loop **slower** (0.23–0.35×) because `numpy.interp` holds the GIL and the per-curve
  work is small, and a fully vectorized multi-curve interpolation is also slower (0.32×). Threads help
  only parallel parquet reads in construction (1.78× on ~5% of construction). The effective parallel
  lever is process-level (the island model, P6.5). Recorded in `notes/performance.md` so the thread
  idea is not re-tried without cause.
- P6.8 (spike, adopted): shared age-grid curve table. Curve breakpoints and offsets are integers, so
  each curve is precomputed at every integer age once (`ws4/sim/curve.py:CurveTable`) and evaluation is
  a 2-D gather; `account_values`, `_curve_value`, the patch/edge criteria, and the block trajectories
  use it (with the `numpy.interp` fallback for a non-integer age). Two adjustments from the spike plan:
  the table is built with one sort-and-slice (not per-curve masking), and `Simulator.reset` now
  invalidates the fragment-to-feature join only when the tracks actually changed. A/B vs the checkpoint:
  `account_values` 12.60 → 2.43 ms/yr (**5.2×**), warm 30-year simulate 0.422 → 0.095 s (**4.4×**), cold
  30-year simulate 0.397 → 0.261 s (the 0.13 s join rebuild now dominates the cold path). Spike branch
  `spike/shared-grid` merged to `feature/p6-performance`; plan and log in `notes/design/ws4-curve-grid.md`.
- P6.9 (spike, adopted): fast fragment-to-feature join rebuild. The rebuild used `np.unique` over ~210 k
  string labels; the feature side is fixed, so it is now precomputed once (sorted feature rows with each
  curve's table row and label code) and a rebuild is a `searchsorted` plus a vectorized expansion. A/B vs
  `p6-joinrebuild-checkpoint`: one rebuild 0.127 → 0.0045 s (**28×**), cold 30-year simulate 0.299 →
  0.129 s (2.3×). Spike branch `spike/join-rebuild` merged to `feature/p6-performance`; plan and log in
  `notes/design/ws4-join-rebuild.md`.
- P6.10 (spike, adopted): incremental route accounts. Haul, maintenance, and volume route accounts are
  additive over blocks, so they join the incremental objective (`Simulator.block_route_accounts` replays
  one block's products and routing into a summary ledger); build cost is not additive and keeps the full
  path. A/B vs `p6-routeinc-checkpoint` (C5, route-target config, 10 years): warm 300-block evaluation
  93.0 → **14.2 ms** (6.5×); the first evaluation is slower (builds the per-block deltas). Spike branch
  `spike/inc-route-accounts` merged to `feature/p6-performance`; plan and log in
  `notes/design/ws4-incremental-route-accounts.md`.
- P6.11 (spike, adopted): faster simulator construction. The per-curve sorted cache `_curves` was used
  only as the non-integer-age fallback after the age table landed; `CurveTable.value` now serves every
  age (exact at integers, linear between, clamped), so `_curves` is removed. A/B vs
  `p6-construction-checkpoint`: construction ~0.55 → **~0.15 s** (3.7×). Spike branch `spike/construction`
  merged to `feature/p6-performance`; plan and log in `notes/design/ws4-construction.md`.
- P6.12 (spike, adopted): faster route-record accumulation. The reporting ledger aggregated
  (volume, count) per (year, destination, route) and did the per-segment pass once per route at flush
  time. A/B vs `p6-routerecord-checkpoint` (C5, 3-year, 300-block, collect=True, warm): ~0.78 → **~0.08 s**
  (~10×), outputs unchanged. Spike branch `spike/route-record` merged to `feature/p6-performance`; plan
  and log in `notes/design/ws4-route-record.md`.
- P6.13 (spike, adopted): adjacency-scoped spatial constraints. The optimizer's spatial penalty scanned
  every topology edge per evaluation; an adjacency index (`_edges_by_block` / `_incident_edges`) now
  scopes it to the harvested blocks. A/B vs `p6-spatial-checkpoint` (C5, 300-block schedule):
  `_spatial_penalty` 163.7 → **13.1 ms** (12.5×), penalties identical (parity test). Spike branch
  `spike/incremental-spatial` merged to `feature/p6-performance`; plan and log in
  `notes/design/ws4-spatial-scoped.md`.
- P6.14 (spike, adopted): faster matrix builder. The builder re-parsed the recipe's huge constant
  `lookupTable(...)` literals on every evaluation; the parsed form is cached by the identity of the keys
  string, `_expand_tokens` skips texts with no `%`, and each stratum's `matching_selects` is memoized.
  A/B vs `p6-builder-checkpoint`: 200-fragment slice 17.7 → **2.2 s** (8.1×); canonical MKRF build
  192.7 → **21.5 s** (9.0×), outputs identical (`compare_matrix`: MATCH). Spike branch `spike/builder-perf`
  merged to `feature/p6-performance`; plan and log in `notes/design/ws4-builder-perf.md`.
- P6.15 (fix, adopted): score product accounts. A target on a raw `product.*` account was evaluated
  against a missing value, because `Simulator.simulate` returned only feature account values and
  `block_trajectory` (the incremental objective's per-block path) ignored products. A year's produced
  products are now summed into the account values (one row per year and account), and products are
  produced in `block_trajectory`, so the incremental and full paths agree cell for cell. On the
  synthetic fixture a `product.Volume` target of `minimum=1000` now yields a penalty of 640 (the exact
  shortfall against the 360 produced) rather than 1000. Branch `fix/product-account-objective`.
  Dashboard on close: **GREEN** (`python scripts/dashboard.py`).
- P6.16 (feature): live target-window watcher. `ws4 watch` runs the same search and paints the
  realized-versus-target window of an account in place — the reference target chart: one column per
  period, the minimum/maximum target band shaded, and the realized value drawn over it, coloured by
  status (green inside the window, red below the minimum, blue above the maximum). Targets are per
  year; the view sums them into periods of `--period-width` years. The optimizer now exposes the
  account values of its latest evaluation (`Optimizer.last_account_values`). `ws4/opt/watch.py` plus
  the `watch` command; tests in `tests/test_watch.py`. Branch `feature/p6-watch`. Dashboard on close:
  **GREEN** (`python scripts/dashboard.py`).
- P6.17 (feature): multi-rotation treatment chains. A block may be treated more than once. The
  optimizer's schedule is now `dict[block, chain]` (an ordered tuple of events); `candidates()` walks
  the track transitions to generate the feasible rotations; `Simulator.block_chain` /
  `block_chain_products` evaluate a chain; the delta evaluator prices a changed block's whole chain;
  and the spatial (`schedule_years` returns every disturbance year per block, green-up across
  rotations) and route (`block_route_chain`) paths are chain-aware. Verified: incremental vs full
  parity 0.000000 for mixed chain schedules (fixture and C5); rotations lift the C5 200-year softwood
  ceiling from **17.74 to 41.02 Mm3** (0.887 to 2.051 Mm3/period), so a 1.3 Mm3/period even flow is
  feasible. Branch `feature/p6-optimizer-core` merged to `feature/p6-performance`; plan and log in
  `notes/design/ws4-optimizer-core.md`. Dashboard on close: **GREEN**.
- P6.18 refinement (post-merge): the operators now move **in place** — they mutate the schedule and
  return an undo record, so a rejected move is undone without copying the whole schedule, and the LNS
  and swap operators sample their blocks by rejection instead of building an O(schedule) list. Warm
  C5 200-year: overall ~2252 → **2478 iters/s**; the default (LNS weight 0.2) **2259 → 2910** (1.29×).
  LNS remains the dominant cost (no-LNS ~5613/s), so the operator weights are now configurable
  (`OptimizeConfig.lns_weight`/`lns_destroy`, and `--lns-weight`/`--lns-destroy` on `ws4 watch` and
  `ws4 optimize`). Dashboard: **GREEN**.
- P6.18 (feature): move-based incremental objective. The evaluator keeps the realized totals per
  `(year, account)` for the target accounts and prices a move by the exact delta it makes, instead of
  recomputing the whole schedule: ~2,000,000 dict updates per move become a few hundred operations.
  With a product fast path (`block_products` / `block_chain_products`), a shared operator option index,
  LNS set membership, and operators that report their changed blocks, C5 (50-year) objective
  evaluations rose from **2.2 to ~730 per second** (~330x); `ws4 watch` is on the fast path.
  Correctness: 0 mismatch over a 300-move path comparison; the delta incumbent follows the same
  trajectory as a full evaluation. Tests in `tests/test_incremental.py`. Dashboard on close: **GREEN**.
- P6.6 (adopted): native kernels. WP6's `≥5×` acceptance had kept the numba path deferred; it was
  re-probed with a real kernel and adopted on its merits instead. `ws4/sim/kernels.py` holds an `njit`
  gather for the per-block product loop, used automatically when numba is installed with a pure-Python
  fallback and exact parity (`tests/test_kernels.py`; `requirements-dev.txt` installs numba so the CI
  gate runs). Same-seed A/B: C5 200-year 690.6 → **774.2 iters/s** (**1.12×**), 50-year 2421 → **2658**
  (1.10×), identical objective. The bigger win in the same change was caching the fragments' numpy
  arrays (no dependency): 50-year 730 → 1797/s (2.5×), 200-year 312 → 617/s (2×). Evidence in
  `notes/design/ws4-performance.md` (WP6). Dashboard on close: **GREEN**.
- P6.17 follow-up (maintainer finding, correctness): two fixes to the even-flow problem. **(1)** The
  candidate years only offered three points per treatment window (begin/mid/end), so the scheduler
  could not place a treatment at an arbitrary operable age — several 10-year periods were structurally
  below the target. Candidates now cover **every year of every window** (later rotations stay sampled,
  capped). **(2)** Targets were per-year; they are now **periodic** (`Target.period_width`): the account
  is summed over the period and compared to the period levels, so the accounting is per period while
  treatments are still scheduled by year. With both, C5 (200-year, 20 periods) even flow reaches a flat
  **0.800 Mm3 every period** (objective 1), and the move-based objective equals a full simulation.
  `Target.period_width` is documented in `docs/reference/optimizer.rst`. Dashboard: **GREEN**.
- P6.17 follow-up (MIP re-validation): the mixed-integer bound anchored each target to a single
  year, so with periodic targets it constrained only the first year of each period. Fixed to sum the
  account over the whole period (`option_contributions` accounts every cell of the period; the
  constraint rows sum the period's deltas). Re-validated on a 20-block rotation-enabled C5 subset
  (80 options, 20 multi-rotation): the model value of the returned schedule equals a full simulation
  exactly (0.000), every random schedule respects the bound (0 violations), and the reported optimum
  is within ~5e-7 relative of the schedule it returns (a mixed-integer solver tolerance). A committed
  test covers periodic targets (`tests/test_mip.py`). Dashboard: **GREEN**.
- P6.5 follow-up (island mode): two fixes so the parallel path is actually usable and correct.
  `_island_search` hardcoded ``warm_start=False`` (each island started from an empty schedule, so it
  never converged — objective 1.6M vs 64 with the warm start); it now honours the configured warm
  start. And the CLI never set ``workers`` (only ``threads``, which was dead), so the process pool was
  unreachable; ``--threads`` now sets the worker count and ``--starts`` was added. Measured on C5
  (200-year, periodic targets, 20k iterations per search): serial 32.7 s; multi-start x8 / islands x8
  **40.7 s for 8x the search** (best objective 14.1 vs 63.8); islands x32 53.2 s for 32x. Near-linear
  wall-clock scaling (~83% at 8 workers). Dashboard: **GREEN**.
- P6.16 follow-up (watcher islands): `ws4 watch --islands N` runs N islands in parallel and paints
  the **global** best (each island streams its incumbent over a queue; the parent keeps the minimum).
  Islands honour the warm start and `--warm-cache`. Convergence measured on C5 (200-year, periodic
  even flow, 16 independent seeds, 20,000 iterations each — all in parallel, ~42 s wall-clock):

  | budget/island | best-of-1 final | best-of-16 final | iterations to match best-of-1 |
  | --- | ---: | ---: | ---: |
  | 2,000 | 1,227,485 | 1,053,039 | 1,700 (1.2x) |
  | 5,000 | 458,912 | 229,743 | 3,500 (1.4x) |
  | 20,000 | 66.5 | 14.1 | 12,000 (1.7x) |

  So islands give better solutions faster (~1.2-1.7x fewer iterations, i.e. less wall-clock since
  they run in parallel) and a better best at the same wall-clock — modest here because the landscape
  is friendly (most seeds reach the same basin). Tests: `tests/test_watch.py`. Dashboard: **GREEN**.
- P6.19 (feature): patch size-distribution targets. Patch accounts were reporting-only; the optimizer
  can now score them. Since they are **non-additive** (a patch spans adjacent blocks), they are priced
  by a new `PatchModel` (`ws4/opt/patch.py`): each block's criterion series is cached per chain
  (`Simulator.block_criteria_series`), the adjacency is indexed by block, `patch_account_values_indexed`
  drops the whole-edge scan (matching `patch_account_values` exactly), and a move recomputes only the
  years it changes. `--patch-accounts` (YAML) with `--topology` enables targets on sub-accounts such as
  `patch.harvest.50_150.area`. Measured on C5 (50-year, 5,648 blocks): full patch reset 2.1 s, then
  **~35 iterations/s** with a patch target, and it optimizes (objective 12.9 -> 11.7 in 400
  iterations). The state is dynamic (`ws4/opt/patch_state.py`): each year keeps its components, areas,
  perimeters, and per-size-class sums, and a move only touches the neighbourhood of the moved block —
  a resize, a merge, a new standalone patch, or a removal/split. `search_distance` (the patch
  account's topology neighbourhood, in metres) scopes the adjacency. Verified cell-for-cell against the
  reporting path and the from-scratch computation over random mutation sequences
  (`tests/test_patch_state.py`, `tests/test_patch_objective.py`). Dashboard: **GREEN**.

## 2026-10-16

- P6.20 (feature): topology cluster operator. Single-block moves rarely reach a harvest-block
  configuration, so `ClusterOperator` (`--cluster-weight`, `--cluster-size`) proposes one move over a
  whole topology neighbourhood and lets the search create or break a patch in a single step. On the
  50-year patch-target problem it reached objective 10.67 at weight 0.5, against 11.60 with the operator
  off, at about 39 iterations/s. Tests: `tests/test_operators.py`. Dashboard: **GREEN**.
- P6.21 (feature): stand-centred opening constraints in the MIP bound. `bound_for` accepts a topology
  and `max_opening_ha`, and `solve_mip` then adds one linear row per stand and year
  (Gunn and Richards 2005, eq. 6) rather than enumerating adjacency covers; a stand whose own area
  exceeds the cap is forbidden (the `A_k+` below-zero case). The bound stays a valid lower bound and
  tightens monotonically as the cap falls: on a 20-block C5 subset over 200 years it is 3,866,245 with
  no cap, 3,884,505 at 80 ha, 3,890,015 at 60 ha, and 3,951,474 at 30 ha, and each returned schedule
  re-simulates to within the mixed-integer tolerance of its bound. The optimizer forwards the configured
  `topology_path` and `max_opening_ha` when `mip_bound` is set. Tests: `tests/test_mip.py`.
  Dashboard: **GREEN**.
- P6.22 (feature): adaptive temperature schedule. The search used a geometric schedule
  (`temperature *= cooling`) whose two constants were fixed at `1000` and `0.99` for every problem, so
  they had to be re-tuned by trial per instance. `ws4/opt/cooling.py` adds the polynomial-time rule of
  Aarts and Van Laarhoven (the schedule Lockwood and Moore 1993 chose over the geometric one): the
  initial temperature is set from the mean uphill move for a target acceptance ratio, and the
  temperature is then decreased from the observed objective spread. `--cooling-mode adaptive` selects
  it (`--cooling-window`, default 64, sets the iterations per temperature); `geometric` stays the
  default. Measured on C5 at equal seeds and iteration budget: on the 200-year even-flow problem the
  mean objective is **64** against **572** for the shipped geometric constants (its best seed still
  wins, 14 against 42), and it matches a hand-tuned geometric factor (0.9995, mean 49) with no sweep;
  on the 50-year patch problem it beats both the shipped and the tuned geometric factors on every seed
  (mean **10.61** against 11.39 and 11.59; best **9.81** against 11.20). Per-iteration cost is
  unchanged (about 3,200 and 59 iterations/s); the adaptive schedule is marginally faster because a
  warmer search rejects fewer moves, and a rejection restores the schedule and reverts the evaluator.
  Tests: `tests/test_cooling.py`, `tests/test_watch.py`. Dashboard: **GREEN**.
- P6.23 (feature): target-weight calibration. Targets of different magnitudes unbalance the
  objective: the largest term dominates and the search freezes before the others are considered
  (Lockwood and Moore 1993 traced each term as the control parameter fell and rescaled them by hand
  until they decreased at similar rates). `ws4 calibrate` runs a short pilot search, records the
  largest penalty each target reaches (`objective_terms` in `ws4/opt/objective.py`), and writes a
  targets file whose weights are rescaled so the peaks match (`balance_targets`, `ws4/opt/calibrate.py`);
  a target that never fires keeps its own weights. It matters when the terms differ in magnitude: on
  C5 with even-flow volume and a patch-size term, the pilot measures the volume peak at 7.7e6 against
  12.9 for the patch term, so the patch term has no effect on the uncalibrated search; after
  calibration the search improves **both** realized terms (volume 9.64e6 to 9.33e6, patch 11.06 to
  9.47). The cost is real: the patch term makes each iteration about 2.3x more expensive, because the
  moves that alter patches are the ones that cost, so the same 2,000 iterations take 117 s against 52 s.
  The pilot must match the run's `--warm-start`, or a term that only appears once blocks are harvested
  never registers. Tests: `tests/test_calibrate.py`. Dashboard: **GREEN**.
- P6.24 (feature): the mixed-integer bound on the command line. `OptimizeConfig.mip_bound` was
  reachable only from the API, so `solve_mip` was unusable from a shell. `ws4 optimize --mip-bound`
  now records the bound, the gap, and the bound status in `summary.json`, and the configured
  `--topology` and `--max-opening-ha` feed the stand-centred opening constraints into it. The
  `optimize` command also gained `--years` (it had no horizon option, so it always ran the 50-year
  default). Tests: `tests/test_optimizer.py`. Dashboard: **GREEN**.
- P6.25 (performance): the patch-account evaluation bottleneck, profiled and partly fixed. A patch
  target costs a 30-70x drop in iterations per second against an additive target on C5, and the cost is
  **graph work on the patch connectivity**, not the objective arithmetic or the criterion curves. Two
  facts dominate: the member graph is one giant component (4,273 of 4,695 members in the largest year
  state), and only **4% of members are articulation points**, so 96% of detaches walked the whole
  component (86% of a single-block move) only to prove it does not split. Fixed an exact early-exit
  connectivity test (`PatchGroupYear._reachable`: walk from one member-neighbour and stop once the
  others are all reached), cached the size-class labels, and inlined the per-block value lookup.
  Single-block moves **37.9 -> 142.5 iterations/s (3.8x)**; the default configuration only 37.2 ->
  43.2/s because it is dominated by the bulk (LNS) rebuild. The remainder is analysed and prototyped:
  the bulk rebuild as a numba CSR kernel is **41x faster** (10.98 ms -> 0.269 ms) with identical
  component areas, and a BFS spanning-tree leaf test proves 65% of detaches cannot split in O(1). The
  full analysis, measurements, kernel, and an ordered plan are in
  `notes/design/ws4-patch-evaluation-bottleneck.md`. `cProfile` misattributes this workload by an order
  of magnitude; the numbers use phase timers. Tests: `tests/test_patch_state.py`,
  `tests/test_patch_objective.py`. Dashboard: **GREEN**.
- P6.26 (fix): patch accounts were representing the wrong thing, twice over, and P6.25's measurements
  were taken on that wrong configuration. An untreated block was priced at criterion `0.0` instead of
  its inventory series, and `PatchModel.reset` skipped it entirely — so with an empty schedule the
  optimizer saw **zero patches** where the reporting path saw 262 (26,384.9 ha). Separately,
  `PatchLedger` ignored `search_distance`, so the report and the optimizer disagreed whenever it was
  set. Both are fixed, and `PatchAccount.search_distance` now defaults to **0.0**: only blocks that
  literally touch (their polygons share a vertex) are neighbours. The topology's `DISTANCE` column is
  the shortest gap between two polygons, so the old `None` default silently joined patches up to 200 m
  across roads and creeks — mathematically valid, never what a resources analyst wants to express. On
  the sample dataset the default keeps 28,727 of 68,586 edges and gives a median patch of one block
  (largest 178 of 2,737 members for `feature.Seral.young`), where the old default collapsed the forest
  into a single 4,273-block patch. With the representation corrected, single-block patch moves run at
  **298.9 iterations/s** (against 37.9 originally) and LNS is the whole of the remaining cost (53%
  `rebuild_local`, 22% `_affected`). Added a monotonicity property test (a larger `search_distance` can
  only merge patches, never split them), an empty-schedule regression test, and reporting-path parity.
  `notes/design/ws4-patch-evaluation-bottleneck.md` was rewritten on the corrected configuration.
  Tests: `tests/test_patch_accounts.py`, `tests/test_patch_objective.py`. Dashboard: **GREEN**.
- P6.27 (performance): `_affected` was not what it looked like. It compares the old and new criterion
  series over every year for every changed block, which reads as a comparison cost, but call counters
  showed `series()` is called 1.25M times per run against only ~11k cache misses: the cost was
  **constructing** a new chain's series, not comparing series. `Simulator.block_criteria_series` was a
  Python loop over every year and, inside it, every fragment calling `_curve_value` — 159 us per call.
  It now fills the horizon in one integer-age gather over the curve table per treatment **event**
  rather than per year, and runs at **58.7 us (2.7x)**. A per-year numpy version was tried first and was
  **not** faster: numpy call overhead on a 50-element array (~1.5 us) matches the Python work it
  replaces, so the vectorisation has to be per event, not per year. Hoisting the per-block series
  lookup out of the per-year loops in `pending`, `_local_cells` and `reset` (it was redone once per
  year for a value that already covers every year) went with it. `_affected` 1.84 -> 0.78 s, the
  default search 41.9 -> **55.7 iterations/s (+33%)**, single-block moves 298.9 -> **387.9 (+30%)**.
  `rebuild_local` is now the only dominant cost (~62% of a bulk move). Tests:
  `tests/test_simulator.py`, `tests/test_patch_objective.py`. Dashboard: **GREEN**.
- P6.28 (decision): the ceiling for the compiled port, measured *before* committing to the refactor.
  Captured real `rebuild_local` calls from a real search on the corrected touching adjacency, then ran
  the Python implementation and an equivalent numba kernel on identical inputs (60 bulk calls, 564
  changed blocks each, ~3,332 members over 12,567 blocks and 57,454 CSR edges). The kernel does the
  relabel plus area and perimeter in **0.279 ms against 6.768 ms in Python — 24.3x** — with zero area
  and zero perimeter mismatches. Marshalling the dicts into arrays per call gives 4.9x, and that still
  excludes writing the result back into the `members` sets, which is roughly half of `rebuild_local`'s
  work; so a dict-marshalling wrapper is worth about **2x, not 24x**. The port therefore has to make
  the arrays the source of truth and drop the `members` sets in favour of `comp` + `count` +
  BFS-on-demand — a simplification of `PatchGroupYear`. The kernel, the design, and the expected end
  to end (about 56 -> 200+ iterations/s) are in `notes/design/ws4-patch-evaluation-bottleneck.md`.
  No production code change in this entry; it is the go/no-go measurement. Prototype harness kept out
  of the repository per the scratch rule. Dashboard: **GREEN**.
- P6.29 (performance): the patch state is array-backed and the bulk relabel is compiled. `PatchGroupYear`
  now holds the membership, criterion value and component of each block in `array.array` (Python
  indexing is about list speed) and hands the numba kernels a **writable zero-copy numpy view**, so a
  bulk relabel needs no marshalling either way; the `members` sets are gone (a component's size is a
  count, a merge re-points by walking `comp`, and a split is found by walking from the removed block's
  member-neighbours, since every resulting piece contains one). New `ws4/opt/patch_kernels.py` holds the
  two relabels, `label_all` (reset) and `label_from_seeds` (a bulk move). Fresh-process A/B, 600
  iterations, C5 at 50 years: the default search **30.0 -> 52.2 iterations/s (+70%)**, and the pure
  single-block path 148.9 -> 113.0 (**-22%**, because the Python walks now do array lookups per edge
  where the dictionaries did membership tests). Measurement discipline is part of the result: a single
  process that runs several configurations warms numba and the caches, so its second configuration can
  read 2-4x faster with no cause, and the in-process numbers in P6.27 and P6.28 are superseded by these
  one-config-per-process runs. Parity is held cell-for-cell against the from-scratch scan by
  `tests/test_patch_state.py`. Tests: `tests/test_patch_state.py`, `tests/test_patch_objective.py`.
  Dashboard: **GREEN**.
- P6.30 (performance): the connectivity walks are compiled too. P6.29's arrays cost the single-block
  path 22%, because its walks then did per-edge array lookups where the dictionaries had done
  membership tests. Those walks — `reachable_from` (the early-exit connectivity test), `component_from`
  (a split's piece walk) and `piece_aggregate` (a piece's area and perimeter) — are now kernels over
  the same CSR arrays, with generation-stamped scratch so nothing is cleared between calls, and the
  `covered` set in `_split` is gone (the first piece's component id is already restamped, so later
  walks cannot re-traverse it). Fresh-process A/B, three runs each, 600 iterations, C5 at 50 years:
  the default **29.6 -> 48.1 iterations/s (+62%)** and the single-block path 153.3 -> 141.2 (**-8%**,
  down from -22%). This supersedes the P6.29 numbers for the walks. Tests:
  `tests/test_patch_state.py`, `tests/test_patch_objective.py`. Dashboard: **GREEN**.
- P6.31 (performance): the bulk relabel reports its own stale components. `rebuild_local` still scanned
  every changed block's neighbourhood in Python (roughly 0.8-1.5 ms of array reads per bulk call) to
  find which component ids to drop; `label_from_seeds` now records the previous component id of each
  changed block and member neighbour as it seeds, so the drop is a set over that list and the scan is
  gone. Also measured the spanning-forest leaf test and decided against it: on the realistic
  configuration only 50.3% (peak year state) and 43.8% (year 25) of the detaches that take the walk are
  leaves of a BFS spanning forest, and the other half would need a full component BFS to repair the
  tree, so it does not pay now that the walks are compiled. Fresh-process A/B, 600 iterations, C5 at 50
  years: the default search **31.0 -> 56.4 iterations/s (+82% against the dictionary implementation)**,
  the single-block path unchanged at -8% (it never uses the bulk path). The walks are no longer a
  measurable cost: the default's time is now `rebuild_local` 43%, criterion `series` lookups 19%,
  `_affected` 15%, and the whole single-block path 4%. Tests: `tests/test_patch_state.py`,
  `tests/test_patch_objective.py`. Dashboard: **GREEN**.
- P6.32 (feature): a binding patch benchmark, and the gap/merge operator. Every earlier patch number
  was measured against a target satisfied at iteration 0 (`objective=0.000`), so it characterised
  overhead on a solved problem rather than the cost of optimising patches. With a binding target
  (`patch.harvest.0_5.frequency <= 60`, year 0) the search drives the penalty from 88 into the low 20s
  over 4,000 iterations, so the optimizer does optimise patches. Added `MergeOperator`
  (`--merge-weight`, default 0): it samples a **gap** — a non-member block whose member-neighbours span
  two or more components, the negative space between proximal patches — and gives it a chain that makes
  it a member in one of the years the objective reads (new `PatchModel.focus_years`; targeting the
  objective's years rather than a random year was worth most of the effect). `is_gap` is `O(degree)` and
  needs no incremental index. Over five seeds at 4,000 iterations the mean final penalty is 16.4
  without the operator and **14.6** at weight 0.5 (three seeds improve, one ties, one worsens), and the
  rate rises from 56-69 to 67-77 iterations/s because a merge move is a single block and displaces
  expensive LNS moves. Tests: `tests/test_patch_objective.py`, `tests/test_operators.py`.
  Dashboard: **GREEN**.
- P6.33 (fix): the split operator, and a correction to P6.32. Added `SplitOperator` (`--split-weight`,
  default 0): it samples a member block that is an **articulation point** of its patch (`is_cut`, the
  same early-exit test a detach uses, O(degree) in the common case) and untreats it, splitting the
  patch. Adding it exposed a flaw in the P6.32 benchmark: with no volume floor, a max-patch target is
  partly satisfied by harvesting less, so the operator comparison was confounded. Re-run with an
  even-flow floor (`product.Yield.managed.Conif` >= 600,000 per 10-year period) and the **patch penalty
  reported on its own** (the total is dominated by the volume shortfall): at 2,500 iterations on two
  seeds the 0-5 count penalty is 24 (mean) without an operator, 22 with merge at 0.5, and 27 with split
  at 0.5. So the merge effect is within noise once the harvest level is constrained, and the split
  operator shows no benefit on this target. Both stay implemented, tested, and off by default. The
  `1000+` cap is not a discriminator either: with a volume floor the default operators already reach
  zero large patches. Lesson recorded: pair a patch target with a volume constraint and report the patch
  term separately, or the operators will look better than they are. Tests:
  `tests/test_patch_objective.py`, `tests/test_operators.py`. Dashboard: **GREEN**.
- P6.34 (feature): the watcher paints several target windows at once. `ws4 watch` accepted repeated
  `--account` flags but **summed** them into a single window, which is useless when the accounts have
  different units (m3 per period and percent of patch area). Each `--account` now gets its own window,
  with its own axis, title and penalty, so a volume target and a patch size-class target can be watched
  converging side by side — the view an analyst uses to see that the search is working and how fast.
  `WatchState.window` became `windows`, and the summary `penalty` is summed across them. A
  **percentage** account (the patch ``…<class>.size`` shares) is averaged over a period rather than
  summed, since a share is not additive; before that fix the patch window read 379% where the truth
  was ~38% and the target looked satisfied. Tests: `tests/test_watch.py` (one window per account, the
  CLI shows both, and a percentage is averaged). Dashboard: **GREEN**.
- P6.35 (performance): patch statistics are computed per **accounting period**, not per year. The
  simulation runs one year at a time but the accounting is periodic, so `PatchModel` now maintains
  component state only at the years a patch target actually reads (`active_years`, taken from the patch
  targets' `cell_years()`), instead of every year of the horizon: `reset` builds only those states and
  `_affected` only looks for changes in them. Everything else is untouched. A patch target at one year
  of a 50-year horizon now maintains **one** state instead of fifty, and the volume-floored patch
  benchmark goes from **62 to 310 iterations/s (5x)** with the patch penalty unchanged (27). Tests:
  `tests/test_patch_objective.py`, `tests/test_patch_state.py`. Dashboard: **GREEN**.
- P6.36 (fix): a patch target spanning a period is read at **one year** of that period. 1 year is the
  minimum time step in WS4 and the accounting is periodic, so a patch account (a snapshot of the map,
  unlike a volume or an area) must not be summed across the years of a period: a
  `period_width=2` patch target was summing a share or a patch count over two years. `IncrementalObjective`
  now reads a patch target at the first year of its period only, for both the objective and the cells it
  tracks, and the patch model keeps only those years. Tests:
  `tests/test_patch_objective.py` (a period-width patch target reads its first year). Dashboard:
  **GREEN**.
- P6.37 (docs): the time-step model is stated where targets are defined. The **simulation step is one
  year and is not configurable** (growth, treatments, transitions, road events); the **account** time
  step is a whole number of years — the period length — set per target by `period_width`, five and ten
  being the planning convention. `Target` now rejects a `period_width` below one year, and the objective
  documentation says plainly that an additive account is summed over its period while a patch account (a
  map snapshot) is read at the period's first year. Tests: `tests/test_optimizer.py`. Dashboard:
  **GREEN**.
- P6.38 (feature): the watch windows sit side by side. `render_frame` laid the target windows out
  vertically, so a volume window and a patch window could not be compared directly. They are now laid
  out in `rich.columns.Columns` (which falls back to stacking by itself on a narrow console), and with
  more than one window the per-period table drops its shortfall and excess columns so two of them fit
  the width — that information is in the penalty in each window's title. `window_table` gained a
  `compact` argument. Tests: `tests/test_watch.py`. Dashboard: **GREEN**.
- P6.39 (benchmark note): the warm start is level-dependent, and a corrected even-flow ceiling.
  Watching the 50-year C5 problem showed harvest spiking in the first and last periods. It is not the
  objective: from a cold start the solver reaches a perfectly flat profile with a penalty of exactly
  **0** in 10,000 iterations. It is the `--warm-start` schedule, which gives every block a year-0
  clearcut; whether that helps depends on the target level against the ceiling — far below it (300k
  against a ~1,500k ceiling) the warm start over-harvests by about 9x and the search spends its budget
  undoing it (13.3M -> 7.2M in 10,000 iterations), while near the ceiling (1,000k over 200 years) it
  starts with roughly the right total volume and only has to redistribute. This also corrects an
  earlier claim of mine that 800k per period is unreachable over 50 years: it is exactly reachable, and
  the measured cold ceilings are **~1,500k** per 10-year period over 50 years and **~1,000k** over 200
  — the short horizon is higher because it can liquidate inventory with no terminal constraint. The
  finding is recorded in `notes/design/ws4-patch-evaluation-bottleneck.md`. No production change.
  Dashboard: **GREEN**.
- P6.40 (fix): period indices are numbered as analysts expect. The watcher labelled the accounting
  periods ``0..N-1``; the established convention reserves **period 0 for the instantaneous
  pre-simulation state** of the forest (a zero-length period), so the simulated periods are ``1..N``.
  `period_label` is now the single source of that mapping for the chart ticks and the period table, and
  the objective documentation states the convention and that a target's `year` is a year, not a period
  index — a target at `year: 0` with `period_width: 10` is the level for period 1, which covers years 0
  to 9. Tests: `tests/test_watch.py`. Dashboard: **GREEN**.
- P6.41 (feature): flow targets — even flow and non-declining yield. Patchworks expresses these as
  derived accounts (`flow.even.*`, `flow.ndy.*`, built with `addFlowRatioAccount` and a `FlowSpec`)
  whose target is **zero with a weight**, so the constraint is on the *flow* rather than the level; the
  level comes from a separate target on the same account, and the C5 scenario script pairs exactly
  those two. ws4 now has the same as a target flavour: `flow: even` sums `|period - mean|` over the
  window and `flow: ndy` sums how much each period falls below the one before it, with
  `flow_start`/`flow_end` (years) clipping the window (default the whole horizon) and `period_width`
  grouping the years. They are period-level terms, so the objective and the evaluator aggregate whole
  periods, the evaluator tracks every year of the window, and the move delta recomputes the term from
  the pending change — the delta still equals a fresh evaluation, including for a flow term. The
  definitions are WS4's own: the first-party documentation gives the call signatures but defers the
  formula to an API document that is not available, so it is documented in the reference and easy to
  change. Tests: `tests/test_flow_targets.py`. Dashboard: **GREEN**.
- P6.42 (fix): the flow-target definitions, corrected to the established ones. `flow: even` is the
  **percent difference of each period from a reference period** — `sum(|100 * (x_p - x_ref) / x_ref|)`,
  the reference being the window's final period unless `flow_reference` names another — and
  `flow: ndy` is the **percent change between consecutive periods**, counting only the declines. P6.41
  had `even` as a deviation from the mean and `ndy` as an absolute decline between periods: wrong on
  both counts. Because both divide by a balance, the term is **infinite while that balance is zero**,
  which is the whole reason for the priming procedure — a run first solves with a linear volume target
  above the sustainable level so every period carries wood, and only then switches the flow account on.
  Verified end to end on C5 (50 years; one linear volume target at 1.5M per period, weight 1): with no
  schedule the term is `inf`; primed it is 102.02 with per-period volumes 1.504 / 1.501 / 1.535 / 1.704
  / 2.095; with the flow term switched on it falls to **0.00** and the volumes become 1.708 in every
  period. Tests: `tests/test_flow_targets.py`. Dashboard: **GREEN**.
- P6.43 (fix): flow targets are priced **per period**. P6.42 summed a flow target's percent values
  and applied the band once to the sum, which made a `minimum: -1` / `maximum: 1` band meaningless —
  nineteen periods of +1% would sum well past 1. The values are now one per period and the target's
  minimum, maximum, weights and shape apply period by period, which is what makes a
  one-percent-either-way safe band work. Two display bugs fell out of the same area: the watcher's
  `Z +` breakdown used the additive pricing for a flow target (printing absurd contributions such as
  `1.16e+07G`) and the account window merged a flow band into the account's *level* window (a `max 1`
  column) — a flow target is a percent term, not an account level, so the window now skips it. Verified
  on C5 (50 years): a 2M linear minimum plus a +-1% band at weight 10000 non-linear converges from a
  ragged primed profile (2.001 / 0.598 / 1.066 / 1.426 / 1.893 M m3) to
  2.00 / 1.96 / 1.97 / 1.97 / 1.98 — every period inside the band, and the level found without being
  specified. `run_watch` also gained an `initial` schedule so a flow run can continue from its primed
  predecessor. Tests: `tests/test_flow_targets.py`, `tests/test_watch.py`. Dashboard: **GREEN**.
- P6.44 (docs): audit the API docstrings and the Sphinx pages against the code. The build was already
  green (`sphinx -W`), but the content had drifted. Fixed on the pages: the even-flow example said
  "the sum of each period's distance from the mean" (the definition P6.42 superseded); the operator
  list named four of the seven registered operators and did not say that `cluster`, `merge` and
  `split` ship at weight zero (a configuration has to enable them); the patch example read
  `patch.harvest.50_150`, which its own size classes do not produce (`50_250`); a patch move was
  "tens of milliseconds" against a measured ~3 ms (62 → 310 iterations/s, P6.35); the API section did
  not render `Target`, `flow_values`, `flow_penalty`, `IncrementalObjective` or `PatchModel` at all;
  `docs/api/index.rst` claimed the API reference is generated from `scripts/`; and the performance
  page had no patch-target figure. Docstrings: a numpydoc pass over all 269 public objects found 93
  incomplete ones. All **56 in `ws4.opt`** are fixed — `OptimizeConfig` (its 40 fields had no
  `Attributes` section, so the optimizer page rendered the configuration with no field help at all),
  the seven operators and `OperatorRegistry` (one-line docstrings, no parameters or return value),
  `TemperatureSchedule.rule`, `Optimizer` and `from_dataset`, `IncrementalObjective`,
  `solve_mip` (`years`, `opening`), `solve_tabu` and `solve_ils` (`initial`), `watch.render_frame`,
  `axis_maximum`, `WatchState.islands`/`blocks` and the `TargetWindow` accessors,
  `patch_state.compactness`/`class_index`, `RunLogger`, and `PatchModel.cell_map`. The 37 remaining
  findings are outside `ws4.opt` and are recorded in `notes/backlog.md` for P7. No behaviour changed
  and no test changed: the audit is reproducible with the same numpydoc pass. Dashboard: **GREEN**.
- P6.45 (tooling): a public-docstring audit and a `docstrings` gate. P6.44 fixed the drift by hand, but
  nothing would have caught it: the docs gate is `sphinx -W`, which fails on a broken reference and not
  on a missing `Parameters` section, and `tests/test_api_docstrings.py` (numpydoc) covered only
  `scripts/`, never the `ws4` package. `scripts/doc_audit.py` is now the oracle for both scopes, with
  four rules: the docstring exists; every parameter is documented and nothing else is; a callable that
  returns a value has a `Returns` section; a section header is preceded by a blank line. It encodes the
  conventions a library cannot know — a dataclass, pydantic model, or plain class may document its
  constructor arguments under `Attributes`, a `Protocol`'s constructor signature is not its own, a
  leading-underscore parameter is private, and the Typer command module is skipped because its docstring
  is the CLI help. Running it against the repository found the **37 remaining findings** that P6.44 had
  left outside `ws4.opt`: undocumented dataclass fields in `ws4.model.types` (10),
  `ws4.io.forest_model_xml` (6), `ws4.sim` (6), `ws4.patch` (5), `ws4.build` (4), and `ws4.roads` (3),
  plus four missing `Returns` sections and one malformed section. All are fixed, so the scope is at zero
  findings: `ws4.model.types` (every model now lists its fields as attributes), the six
  `forest_model_xml` dataclasses, `Model.empty`, `Table.required_columns`, `IncrementalObjective`, its
  `objective` property, `TargetWindow.n_periods`, `Simulator.account_values`, `Simulator.from_dataset`,
  `write_patch_metrics`, `CurveTable.row`, `PatchLedger.frame`/`write`, `load_block_topology`,
  `RouteNetwork.destination_names`, `matching_selects`, and `transition_key`. The gate is wired into
  `scripts/dashboard.py` (so every commit and the dashboard CI job enforce it) and into the CI checks
  job beside the docs step; a gate was added rather than tightened, and `AGENTS.md` was not changed.
  Tests: `tests/test_doc_audit.py` makes each code fire on a fixture (`MISSING`, `PARAMS`, `STALE`,
  `RETURNS`, `SECTION`, `IMPORT`) and asserts the real scope clean, so the gate cannot pass by checking
  nothing. Dashboard: **GREEN** (seven gates).
- P6.46 (verify): the flow definitions, checked against the established specification instead of
  inferred. P6.41–P6.43 chose the formulas from the first-party call signatures, which defer the
  arithmetic to an API document that was not available; that document is in the extract after all, and
  it settles every open question. `even()` compares **every period with the final one** (period 0, the
  state before the simulation, is not compared), and `ndy(low, high, offset)` compares a selected
  period with the period at that offset — the sample scenario uses offset `-1` over its last periods,
  so the denominator is the **previous period**, which is what ws4 already did. The accounts are
  created with a factor of **100**, so the values are percentages, which is also what ws4 did. Two
  things were wrong, one behavioural and one documentary:
  **behaviour**, the established window includes its first period, which is measured against the period
  immediately before the window; ws4 skipped that comparison when the window did not start at the
  horizon, so the first year of a closing-inventory window was unconstrained. `flow_values` now seeds
  a non-declining series one period earlier, and a window starting at year 0 still has no predecessor
  and so contributes no value for its first period.
  **documentation**, the reference's non-declining example set `maximum: 0`, which charges growth as
  well as decline. The idiom is a **two-sided percent band**: the value is the percent change from the
  previous period, so a minimum of `-1` lets a period come in one percent below its predecessor before
  anything is charged and a maximum of `1` mirrors it, the lower side being the one that usually maps
  to a policy; the strict closing-inventory form is a minimum of `0` with **no maximum**, which is what
  the first-party sample does, so growth is free there. The reference now states the verified
  correspondence, both idioms, and the one presentational difference — `flow_end` is exclusive here
  while the established argument is inclusive.
  Tests: `tests/test_flow_targets.py` gains the window's first period compared with the period before
  it, a window starting at the horizon having no predecessor, and a two-sided band tolerating a
  percent either way while charging what falls outside it; the idiom test pins that a maximum would
  charge growth. Dashboard: **GREEN**.
- P6.47 (metadata): the repository's history is rewritten so that every commit is authored **and**
  committed by the maintainer, who takes responsibility for the work to date. `git filter-branch
  --env-filter` over `main` and `feature/p6-performance` (103 commits) changed only the author and
  committer identity: the trees are byte-identical (`git diff` against the pre-rewrite tips is empty),
  the author and committer dates are preserved, and the commit counts are unchanged (8 on `main`, 95 on
  the branch). A pre-rewrite backup of both branches is kept locally (`backup-pre-rewrite-main`,
  `backup-pre-rewrite-feature`) and `refs/original/` holds filter-branch's own copy.
  Because every SHA changed, the **32 commit citations** in `ROADMAP.md`, `CHANGE_LOG.md`,
  `notes/reports/p0-p5`, and the `notes/design/` pages were refreshed to the new SHAs; a sweep of every
  hex token in the tracked files leaves 62 that resolve to a commit and 25 that are run IDs or numeric
  literals, none of them dangling citations. The 11 `p6*-checkpoint` tags were re-pointed at the
  rewritten commits with the short SHA in each message refreshed, the tagger set to the maintainer, and
  the tagger dates preserved.
  The git identity is now global (`user.name` / `user.email` = the maintainer) with the repository-local
  override removed; it had been `FRESH Lab Agent <noreply@example.org>`. `.git/config` is not tracked.
  Two limits are recorded rather than fixed: `v0.1.0` was **not** moved, because a GitHub release is
  attached to it and moving a release tag needs its own approval (it still points at the pre-rewrite
  history, which keeps those objects reachable), and issue and pull-request authorship cannot be
  rewritten server-side — it is already the maintainer's account, and the three open pull requests are
  the dependency bots'. Dashboard: **GREEN**.
- P6.48 (docs): documentation for human users — getting started, task guides, and an examples gallery.
  The reference pages were contract-shaped and assumed a reader who already knew the tooling; nothing
  walked a new user from an install to a result. The docs now follow the three-audience framing the
  sibling project uses: a landing page that says who each section is for, a **Getting started**
  section (installation; a command-line quickstart; a Python-API quickstart; a complete small study
  with hand-checkable numbers; how the layers fit together, with a data-flow diagram), **How-to
  guides** shaped *prerequisites → procedure → troubleshooting* (prepare a dataset, write targets,
  even flow and non-declining yield, patch size-distribution targets, route products, watch a run,
  automate a study, FAQ), **Guides** (troubleshooting, limitations and boundaries), and an
  **Examples gallery** of executed notebooks rendered with their output. Both entry points are
  first-class: every applicable guide shows the command-line path and the Python path, and the
  architecture page names what each is for. The notebook gallery lives in `examples/` (three
  notebooks: an environment check, the quickstart walkthrough, and the even-flow procedure) with its
  outputs committed, wired into Sphinx through a symlink and `nbsphinx_execute = "never"`; `docs`
  gains `nbsphinx` and `sphinxcontrib-mermaid`, and the three CI jobs that build the docs install
  pandoc, which nbsphinx needs (the host was given the same install for local builds).
  Writing the pages surfaced four inaccuracies, which are fixed here: the route model **is**
  incremental for haul, maintenance, and volume accounts (only a build account, a duplicate account,
  or edge contrast forces a whole-schedule evaluation), which the roads and performance pages and the
  new guides now say; `docs/reference/roads.rst` still called that work "the next effort"; the
  non-declining example set a maximum of zero, which charges growth; and the API page's claims about
  evaluating a schedule are now stated precisely. Two command-line gaps are recorded in
  `notes/backlog.md` rather than papered over: `ws4 optimize` requires a `--weights` file that nothing
  reads and has no `--iterations`, and `Optimizer.last_account_values()` is empty after `run` on the
  incremental path. Every command, snippet, and notebook output in the new pages was executed against
  the repository's own examples, and the numbers shown (340 m3, the ragged-to-flat even-flow profile)
  are the ones the runs produced. Dashboard: **GREEN**.
- Queued the Phase 6 close-out: pull request #81 (`feature/p6-performance` into `main`) and the report
  `notes/reports/p6-closeout.md`. The report recommends the squash merge, deleting the branch, closing
  parent issue #60, and launching P7 (parity and the analyst workflow). It records the acceptance
  evidence — 0.108 s for the C5 30-year simulate, 0.685 s for the 3-year simulate with routing, 29 / 39
  / 31 ms per year for patch accounts, edge contrast, and core area, a 0.003 ms incremental move, and
  6.4x / 15.3x island throughput at 8 and 32 islands with parallel multi-start reproducing the serial
  result exactly — plus the deviations (23 spike commits without a task ID, the `--weights` and
  `threads` gaps, the dependency pull requests the authorship rewrite closed) and the one settings
  change still needing approval, moving the `v0.1.0` release tag into the rewritten history.
  Dashboard: **GREEN** (seven gates).
- Carried out the Phase 6 close-out: pull request #81 squash-merged as `f5d6f27`, the branch
  `feature/p6-performance` deleted, and parent issue #60 closed. The close-out report is
  `notes/reports/p6-closeout.md`, and its acceptance evidence is the fresh C5 benchmark (0.108 s for
  the 30-year simulate, 0.685 s for the 3-year simulate with routing, 29 / 39 / 31 ms per year for
  patch accounts, edge contrast and core area), the incremental move cost (0.003 ms, and 1,006
  iterations/s on a binding volume-plus-patch workload), and island scaling (6.4x at 8 islands, 15.3x
  at 32, with parallel multi-start reproducing the serial result exactly). One settings change from the
  report is still awaiting approval: moving the `v0.1.0` release tag into the rewritten history.
- Launched Phase 7 (Parity and the analyst workflow): parent issue #82, branch `feature/p7-parity`,
  and five child tasks (#83 to #87) — the command-line gaps (`--weights` and `--iterations`), the
  `threads` setting and a scaling re-measurement, a sample estate under `examples/`, the missing
  notebooks and a concepts section, and patch performance under a dense harvest. Dashboard: **GREEN**.
- P7.1 (fix): the two command-line gaps the Phase 6 close-out recorded. `ws4 optimize` required a
  `--weights` file that nothing read, and had no way to set the search budget while `watch` and
  `calibrate` both take `--iterations`. `--weights` is now optional and documented as accepted for
  compatibility — the weights that apply are each target's `min_weight` and `max_weight`, which
  `ws4 calibrate` rescales into a targets file — and `ws4 optimize` gains `--iterations`, defaulting to
  the 500 the configured default already used, so existing runs are unchanged; the issue proposed
  defaulting like `watch` (2000), which would have silently lengthened every run. `OptimizeConfig`'s
  `weights_path` docstring, the reference page, the how-to guides, the FAQ and the limitations page now
  say the same thing, and every example that passed the no-op flag no longer does. `ws4/cli.py` also
  gained a `__main__` guard, so `python -m ws4.cli` works without relying on the console script being
  on `PATH`, which is what the new tests use. Tests: `tests/test_cli.py` covers the framework scripts
  and now the `ws4` command too, with four checks — optimize runs with no weights file, `--iterations 7`
  is honoured in `summary.json`, a weights file is still accepted, and the help marks only the dataset,
  the targets and the output as required. The notebook gallery, the docs and the example commands were
  re-run. Dashboard: **GREEN** (seven gates).
- P7.2 (fix): apply the `threads` setting, and re-measure the island scaling with it in place.
  `OptimizeConfig.threads` was documented as the number of BLAS and worker threads and read by nothing;
  it is now applied wherever an optimizer is built, which covers the parent and every worker process.
  Two mechanisms are needed because the obvious one does not work: the environment variables cover
  libraries loaded later and are inherited by children, but a **forked worker inherits its parent's
  already-initialised BLAS**, so setting them in the child is too late; `threadpoolctl` retunes the
  pools already loaded in the process, which is what pins a worker. It joins the `opt` extra and
  `requirements-dev.txt`; without it the environment is still set and the configuration still records
  the request. The default of one thread per process is measured, not assumed: a single island ran at
  1 037 iterations/s with one thread and 1 033 with eight, and 32 islands ran at 13 660 and 14 385
  pinned against 12 318 and 15 877 unpinned, so BLAS parallelism neither helps nor hurts the search
  and a pool of one-thread processes cannot oversubscribe the machine. **The scaling limit is not
  BLAS**: the same 32-island configuration reaches 13x to 16x while the host's load average moved
  between 4 and 65 during the session, so the criterion stays "met with a stated limit" — now with the
  limit diagnosed, both tables carrying the load they were taken at, and a follow-up recorded for a
  shared or mmapped dataset to cut the memory traffic the processes contend for. `threads` also has a
  CLI help string and a docstring that say what it does. Tests: `tests/test_optimizer.py` adds two —
  the setting limits the pools and the environment of the process it runs in, and the default is one
  thread per process. Dashboard: **GREEN** (seven gates).
- P7.3 (docs, examples): a sample estate under `examples/estate`, so the guides and the notebooks stop
  depending on a two-block toy or on files the reader has to supply. It is a 64-block 8 x 8 grid: one
  clearcut treatment that can be applied more than once (so a rotation is possible), a seral feature
  that marks fresh openings for the patch accounts, the grid topology, a road network with two mills at
  opposite ends (so the least-haul-cost destination differs across the estate), the route
  configuration with per-mill haul and volume accounts plus the duplicate that totals them, a patch
  account with five size classes, and a README that says what each file is for and how to run each
  use. Verified end to end: build and validate, a simulation that forms four openings (80.5 ha, the
  largest 50.4 ha) and splits its 8,793 m3 between both mills by haul cost, and a 20,000-iteration
  search that schedules 57 blocks over rotations. **The shipping exposed a real defect**: the search's
  own view of the patch accounts reads zero for a schedule whose openings exist, so its objective and
  the run's `report_targets.csv` disagree with a simulation of the same schedule (0% against a 62.6%
  share, a 1.8M penalty that a simulation does not charge). That is filed as P7.6 (#88) with the
  evidence and a suspicion about where the criterion series is built, the patch how-to states it
  plainly and points readers at the simulation and the run report, and the README repeats it. The
  estate also gained `tests/test_example_estate.py`, which pins the compile, the openings, the route
  split across both mills, and the patch metrics, and the notebook gallery gained
  `030_sample_estate.ipynb`, executed with its output. Dashboard: **GREEN** (seven gates).
- P7.6 (fix): a patch target was reported as unmet however well the search had done. The search was
  right — a simulation of the incumbent and the incremental evaluator agreed to the hundredth (11.87 /
  16.20 / 71.93 percent across the three classes) — but `Optimizer.run` replays its incumbent through
  the simulator for the report, and it did not pass the patch accounts to that replay. Patch accounts
  are not additive, so the simulator keeps them out of the account values; the report therefore priced
  a patch target against a missing row: a zero share carrying its whole penalty (1.8M in the sample
  estate's case) while the summary's own objective was zero. The fix passes `patch_accounts` (and the
  opening and green-up rules, which were missing from the replay for the same reason) to the
  simulation, and folds `patch_accounts.csv` into the values the report prices, since a patch target's
  account is not among the additive ones. The sample estate's report now shows the 71.93 percent share
  the search found, status `met`, penalty zero. Tests: `tests/test_patch_objective.py` gains the
  regression — a 2 000-iteration run on the sample estate must report a non-zero share with status
  `met` and an objective at zero — verified to fail with the fix reverted and pass with it. The notes
  claiming the mispricing in the patch how-to, the estate README and the notebook are replaced by what
  the run now does. Checking the published figures: nothing needs restating, because the P6 patch
  numbers came from the benchmark and the watcher, both of which read the search's own values, and no
  recorded acceptance figure was taken from a run's report. Dashboard: **GREEN** (seven gates).
- P7.5 (fix, measurement): `Optimizer.last_account_values()` is now populated after a run, on both
  value paths — the incremental builder recorded nothing, and the full builder was the only one that
  did — so a caller can read the incumbent's account values without rereading the run directory, with
  the accessor's docstring saying what it holds mid-search (an `IncrementalObjective`'s
  `values_frame`). The dense-harvest measurement, recorded in
  `notes/design/ws4-patch-evaluation-bottleneck.md`, produced a result worth having: on the same C5
  workload the **patch** run is faster than the volume-only one (60.6 against 25.9 iterations/s),
  because the patch ramp keeps the schedule sparse (60 treatments against 125) and a move costs what
  the schedule touches. A 100-iteration profile of the binding case puts the time in
  `block_criteria_series` (12,636 calls, one per distinct (block, chain) explored, each a Python loop
  over that block's fragments), `PatchGroupYear.__init__` (20 calls at ~48 ms) and `_chains` — that is,
  in the setup and the criterion series, **not** in the incremental relabel the earlier work in that
  note optimised. So the lever is a vectorised series and a lazily built state for the years a search
  reads; neither is done, and the measurement is the baseline to judge them against, recorded in
  `notes/backlog.md`. Tests: `tests/test_optimizer.py` asserts the accessor is empty before any
  evaluation and holds the incumbent's values after a run. Dashboard: **GREEN** (seven gates).
- P7.4 (docs): the patch, route and sweep notebooks, and a concepts section. The gallery gains three
  executed notebooks. `040_patch_targets` sets a ramp on the 50-150 ha class over the sample estate
  with the shape-aware operators weighted, and shows the search meeting 25 and 50 percent at 63.8
  percent, falling short of 75 (which a squared miss at weight 2000 prices at 249 340), and holding the
  shares steady across the horizon because the 40-year rotation keeps refreshing the openings into the
  same class — the P7.6 fix is what makes its report agree with the search. `050_routes_and_mills`
  routes a schedule over the estate's two mills, reads the volume and haul split per destination and
  the route accounts in the values, then constrains the haul cost in a search. `060_parameter_sweep`
  sweeps the volume floor and collects the objective, the treatments, the realized volume and the patch
  status into a frame, which is the automation pattern the how-to describes. All three drive the CLI
  through a small subprocess helper rather than shell magic, so they run headless and lex as Python.
  A **Concepts** section joins the documentation, in the role the sibling project's textbook plays:
  four pages on the model (fragments, blocks, strata, tracks, treatments, rotations), the simulation
  (the annual step, the age-grid curves, operability windows), the accounting (the year clock against
  the period clock, and period 0 as the pre-simulation state), and the objective (targets, weights, and
  the three shapes of constraint: a level, a flow, and a map). It is indexed from the home page and the
  agent index, and each page links into the reference for the detail. Dashboard: **GREEN** (seven gates).
- Queued the Phase 7 close-out: pull request #89 (`feature/p7-parity` into `main`) and the report
  `notes/reports/p7-closeout.md`. The report recommends the squash merge, deleting the branch, closing
  parent issue #82, and launching P8 (verify the replacement claim). It records the acceptance evidence
  — the two command-line gaps closed with four behavioural tests, `threads` applied with the island
  scaling measured and its load recorded, the sample estate used by two guides and four notebooks, and
  the dashboard green at every commit — plus the phase's supporting results (the patch-account
  correction, the dense-harvest measurement and the named bottleneck) and its deviations: the scaling
  criterion met with a stated limit, `--iterations` defaulting to 500 rather than the 2000 the issue
  suggested, P7.6 initially misdiagnosed as a search bug when it was the run's report, and the
  dense-harvest path measured rather than improved. No settings change is pending. Dashboard: **GREEN**
  (seven gates).
- Carried out the Phase 7 close-out: pull request #89 squash-merged as `1dc2c97`, the branch
  `feature/p7-parity` deleted, and parent issue #82 closed. The close-out report is
  `notes/reports/p7-closeout.md`, and its acceptance evidence is the two command-line gaps closed with
  behavioural tests, `threads` applied with the island scaling measured and its load recorded, the
  sample estate used by two guides and four notebooks, and the dashboard green at every commit. The
  phase's most valuable result was not a feature: shipping the sample estate exposed that
  `Optimizer.run` replayed its incumbent without passing the patch accounts, so a patch target was
  reported as a zero share carrying its whole penalty while the summary's own objective was zero — the
  search had been right. No settings change was involved.
- Launched Phase 8 (Verify the replacement claim): parent issue #90, branch `feature/p8-verify`, and
  four child tasks (#91 to #94) — a parity harness against the reference implementation's outputs, the
  C5 results reproduced from documented inputs, the criterion-series and patch-state performance lever
  that P7.5 named, and island scaling measured on a host whose load is recorded. Dashboard: **GREEN**.
- P8.1 (verify): a parity harness against the reference implementation's own outputs. The reference
  sample ships `cost_destination.<mill>.csv`, the summed haul rate from each network node to each mill
  (`-1` where it cannot reach one), which is exactly the quantity WS4's route model computes from the
  same tables — so the comparison tests the **routing**, not the data. `scripts/acceptance.py` gains a
  `parity` check and a `--roads-sample` option: it loads the reference's network, computes WS4's
  least-haul-cost route for every block and mill, and compares the sums node by node, treating the
  reference's `-1` as WS4's no-route and allowing 1e-6. **It found no differences**: on the C5-class
  sample (36 722 segments, 27 231 vertices, three mills, 12 568 blocks) WS4 agrees with the reference on
  all **37 701** node-and-mill pairs a block is linked to, including every node the reference marks
  unreachable. The decision and the limits are in `notes/design/ws4-parity-harness.md`, which states
  plainly what is **not** covered: the sample ships no account report, so "the same schedule produces
  the same accounts in both tools" remains undemonstrated — the largest remaining gap in the replacement
  claim — and build and maintenance costs are not compared against the reference either. Tests:
  `tests/test_acceptance.py` covers agreement, a wrong haul cost, a reachability disagreement, the skip
  path, and a path that is not a directory. Dashboard: **GREEN** (seven gates).
- P8.2 (verify): the C5 figures reproduced from documented commands. The Phase 6 acceptance numbers were
  measured interactively, against a sample that is not in the repository, so `docs/reference/performance.rst`
  now names what the sample must contain, gives the three invocations verbatim (30-year, 3-year with
  routing, and the 30-year spatial run whose per-year figure is the sum divided by the horizon, since a
  single year carries about 0.3 s of setup), and separates the figures that **travel** — the counts,
  which a re-run must reproduce exactly — from the ones that do not, which are every timing and need the
  machine and its load recorded with them. The re-run on the same 72-core host at a load average of 4.65:
  16 174 fragments exactly; the 30-year simulate 0.113 s against 0.108 recorded; the 3-year simulate with
  routing 0.576 s against 0.685; patch accounts 28 ms per year against 29; edge contrast 1.147-1.251 s
  against 1.157; one objective evaluation 0.500-0.754 s against 0.681; peak memory 487-504 MB against
  496. Everything reproduces within the noise of a shared host and the one exact count is exact, so no
  recorded figure needs restating. Recorded in `notes/performance.md`. Dashboard: **GREEN** (seven gates).
- Added P8.5 (#95) to Phase 8: compare WS4's accounts against a reference report. P8.1 established the
  largest remaining gap in the replacement claim — the reference sample ships no account report, so
  "the same schedule produces the same accounts in both tools" is undemonstrated — and this task makes it
  a deliverable: specify the report the comparison needs, extend the parity harness to check one, and
  document how the reference produces it. Producing the report needs the reference implementation, which
  is outside the repository.
- P8.5 (investigation): pinned down the sample the parity comparison will run on, and recorded why the
  newest installer cannot supply it here. The lab's installer carries a C5 demonstration model; the
  build extracted on 2026-10-14 (from the 2019 installer) is what every C5 figure in the repository was
  measured against, including the routing parity comparison. A newer installer (inner executable dated
  2026-07-29) arrived on 2026-10-18, but neither `innoextract` 1.9 (its current release) nor its
  development build, which supports Inno Setup up to 6.3.3, can read it: both report "unexpected setup
  loader revision: 2" and a loader checksum mismatch, so it is a protected or non-standard build and its
  sample has to come from an installed copy. Parity needs the **same** sample on both sides rather than
  the newest one, so the comparison can proceed on the extracted sample, or on the newer one once it is
  zipped from the installed Windows copy. The scenario the reference must run is also specified:
  a **fixed** schedule — blocks, treatments and years pinned in a scenario file — with the account values
  reported per period, and a no-treatment case first, since that exercises the curves, tracks and strata
  with no scheduler in the way. Recorded in `notes/design/ws4-parity-harness.md`. Dashboard: **GREEN**
  (seven gates).
- P8.5 (verify): the accounts comparison, ready for the reference's export. `scripts/acceptance.py`
  gains an `accounts` check with `--accounts-report` and `--accounts-dataset`: it reads the reference's
  own `schedule.csv` (block, treatment, year, with loose column-name matching) and `account_values.csv`
  (year, account, value), replays **that schedule** in WS4, and compares every account-year cell both
  sides report at a relative tolerance of 1e-4 — the tolerance because a reference export is typically
  rounded where WS4's values are not — reporting an account only one side has as its own kind of
  difference, since that is the kind of finding the comparison exists for. Replaying the reference's
  schedule rather than comparing two optimizers' schedules is the design decision: the two searches
  choose differently, so only a shared schedule makes the accounts comparable, and it isolates the
  simulation — which is what the replacement claim rests on. The chosen sample is the one already
  extracted (from the 2019 installer), the same one every C5 figure here was measured against. What
  remains unverified is stated in `notes/design/ws4-parity-harness.md`, which now carries the export
  specification and the exact commands, including a no-treatment case to run first. Tests:
  `tests/test_acceptance.py` covers a report WS4 produced itself reproducing cell for cell, a perturbed
  value failing, a missing column being reported rather than raised, and the skip path. Dashboard:
  **GREEN** (seven gates).
- P8.3 (performance): the criterion series, made cheaper. P7.5's profile had put 64% of a
  `block_criteria_series` call inside the function body rather than in the numpy it calls, so four
  mechanical changes went there, none of them altering what is computed: `asarray` instead of `astype`
  where the fragment arrays already carry the right dtype; one `np.arange(years)` per call instead of
  one per treatment segment; `dict(enumerate(series.tolist()))` instead of a Python call per year; and
  the `present` mask applied only when it can matter. Measured on the same machine, minutes apart,
  with the change stashed and restored, best of three runs of 20,000 calls on the sample estate:
  **58.6 -> 41.5 us per call (-29%)**, the function's own profile time 0.116 -> 0.055 s (-53%), and on
  the C5 patch-ramp workload **60.6 -> 73.3 iterations/s (+21%)** (volume-only 25.9 -> 28.2). Results
  are identical: 53 tests over the patch model, state, accounts, simulator and incremental objective
  pass unchanged, including the one pinning the estate's deterministic patch search, the routing parity
  comparison still agrees on all 37,701 node-and-mill pairs, and the series' values were asserted
  unchanged for no treatment, one cut and two cuts. The lazy-state subtask resolved as **nothing to
  skip**: the states built are exactly the years a patch target reads, which P6.35 already restricted,
  so making each state cheaper is a separate question — recorded, with `CurveTable.gather`'s per-call
  `np.clip`/`iinfo` as the next candidate, in `notes/design/ws4-patch-evaluation-bottleneck.md`.
  Dashboard: **GREEN** (seven gates).
- P8.4 (verify): island scaling re-measured at a known load, and the limit identified. P7.2's figure came
  from a host whose load moved between 4 and 65, so the same binding workload (a volume floor plus a
  patch ramp, 4,000 iterations per island, one thread each) was re-run with the load recorded every
  time, on a two-socket 36-physical-core host: 1 island 1,055 iterations/s, 4 islands 3,238 (77%
  efficiency), 8 islands 6,014 (71%), 16 islands 9,432 (56%), 18 islands 11,782 (62%) and **32 islands
  18,685 iterations/s = 17.7x at 55%**. Efficiency is already down to ~56% at 16 islands, half the
  physical cores, which rules out the explanations the earlier notes carried: the BLAS pools are
  measurably neutral (P7.2), the per-process setup is ~1 s against 4-7 s of search, and 16 processes on
  36 physical cores share no SMT siblings, while the CPU accounting shows each process holding roughly
  one core (at 32 islands, 185 s of user time against a 6.85 s wall, and the same CPU per island as a
  solo run). The limit is therefore the memory hierarchy — bandwidth and last-level-cache contention,
  with traffic crossing between the two sockets — and more islands still win in absolute terms, so the
  criterion stays met *with a stated limit*, now with its cause measured rather than suspected. One
  finding recorded for the obvious next experiment: the simulator **writes** to the fragments frame it
  inherits (`self.fragments["offset"] = ...`), so a forked worker's copy-on-write pages are copied
  anyway and a shared or mmapped dataset would need a read-only simulation state to help. Recorded in
  `notes/performance.md` and on the performance reference page. Dashboard: **GREEN** (seven gates).
- Queued the Phase 8 close-out: pull request #96 (`feature/p8-verify` into `main`) and the report
  `notes/reports/p8-closeout.md`. The report records the four acceptance criteria as met — the routing
  parity comparison (no differences in 37,701 node-and-mill comparisons against the reference's own
  per-node haul costs), the C5 figures reproduced from documented commands within the noise of a shared
  host with the one exact count exact, the criterion series made cheaper (58.6 -> 41.5 us per call, the
  C5 patch-ramp workload 60.6 -> 73.3 iterations/s, identical results), and island scaling re-measured
  at a recorded load (17.7x at 32 islands, 55% efficiency) with its cause measured as the memory
  hierarchy after BLAS, the per-process setup and SMT were each excluded by measurement — plus the
  deviations (the format-gate slip on the first P8.3 commit, the 2026 installer being an unextractable
  protected Inno build, and P8.4 answering the memory question by measurement rather than by a change)
  and a P9 recommendation of spatial performance and memory. **#95 is deferred to P9** rather than
  holding a ready phase open on an external input: the accounts comparison is built, tested and
  documented, its sample is packaged with digests, and only the reference's export is missing. Dashboard:
  **GREEN** (seven gates).
- Carried out the Phase 8 close-out: pull request #96 squash-merged as `e8b5248`, the branch
  `feature/p8-verify` deleted, and parent issue #90 closed. The close-out report is
  `notes/reports/p8-closeout.md`; its acceptance evidence is the routing parity comparison (no
  differences in 37,701 node-and-mill comparisons against the reference implementation's own per-node
  haul costs), the C5 figures reproduced from documented commands with the one exact count exact, the
  criterion series made 29% cheaper for +21% on the C5 patch-ramp workload, and island scaling
  re-measured at a recorded load (17.7x at 32 islands) with its cause measured as the memory hierarchy
  after BLAS, the per-process setup and SMT were each excluded by measurement. It was the first phase
  whose pull request was green on its first CI run.
- Launched Phase 9 (Spatial performance and memory): parent issue #97, branch `feature/p9-memory`, and
  five child tasks — share the dataset across worker processes (#98), re-measure island scaling with it
  shared (#99), make the patch-state construction cheaper (#100), stop rebuilding bounds in every curve
  gather (#101), and the accounts comparison against a reference report (#95, carried from Phase 8 and
  renumbered P9.5 as a sub-issue of the new parent). Dashboard: **GREEN**.
- P9.1 (performance): one copy of the dataset for the parallel pool. Measured first: a worker costs about
  **0.98 s and 170 MB** to start on the C5-class sample (`from_dataset` 7 ms, `simulator()` 195 ms and
  +63 MB, `candidates()` 539 ms and +90 MB, `patch_model()` 243 ms and +18 MB), so a 32-island run builds
  about 5.4 GB of private state it could be sharing. `Optimizer` now touches those caches before it
  creates a worker pool, so a **forked child inherits them copy-on-write**: a probe of the child's memory
  reports **174 MB shared and 2 MB private**, against ~65 MB of private dataset pages when it loads its
  own. Stated plainly: this does **not** change wall time, because the workers' loads already run in
  parallel and sharing removes work from each process without shortening the critical path — measured at
  8 and 32 islands with a 200-iteration budget, before and after, at loads rising from 15 to 19:
  3.97/3.42 s against 4.02/3.95 s at 8, and 5.51/6.58 s against 5.76/5.73 s at 32, overlapping. The
  effect it targets is memory traffic, which is what P9.2 measures on the curve. The patch model is
  deliberately not preloaded: the evaluator builds its own per worker, so sharing it needs a change to
  ownership rather than a preload, recorded as a separate question. Dashboard: **GREEN** (seven gates).
- P9.2 (performance, #99): re-measured island scaling and **rejected the P9.1 preload**. A paired,
  order-alternated comparison (ABBA, three pairs per island count, because a first pass that always ran
  the control first inherited a host load climbing from 5 to 16 and produced the same ~10% change from
  load alone) shows the preload costing a median **-12.2%** at 16 islands and **-12.7%** at 32, with the
  one-island pairs scattering +1.7/-4.4/-8.4% as they should where no pool is created. The cause is
  measured, not inferred: a worker never uses the parent's state — `_island_job` builds its own
  `Optimizer.from_dataset(...)` — so the preload shares nothing a worker reads and its **0.789 s** of
  serial setup lands entirely on the critical path, predicting 10,324 it/s at 16 islands and 16,904 at
  32 against observed 10,215 and 16,823. P9.1's own probe measured the wrong path: it called the
  inherited optimiser's methods, which a worker does not do. The preload is **removed**, the control
  curve reproduces P8.4 (1,089 it/s at one island against 1,055; 18,870 at 32 against 18,685), and the
  honest conclusion is recorded instead — sharing pages saves capacity this host does not need and
  cannot reduce the bandwidth contention P8.4 measured, since every process still reads the same bytes.
  The option that would genuinely share one copy (handing the pool a read-only built state) is in
  `notes/backlog.md` with no throughput claim. Dashboard: **GREEN** (seven gates).
- P9.3 (performance, #100): **the patch-state construction, 25.9 ms -> 2.79 ms per state (-89%), and the
  C5 patch-ramp workload +5.9%** (86.9-88.2 -> 92.7-92.9 iterations/s), with a full 100-group-year
  reset down from 3.27-3.50 s to 0.68-0.71 s (-80%). Profiling one state on a C5-class group
  (12,567 blocks, 28,727 edges) showed the time was not in anything per-year: 45 ms of self time in
  `PatchGroupYear.__init__`, of which 21 ms is 114,908 `array.array.append` calls and 15 ms is 85,288
  `dict.get` calls — the CSR adjacency marshalling, identical in every year of a group, and read-only
  to the kernels (`label_all`, `label_from_seeds`, `reachable_from`, `component_from`,
  `piece_aggregate` take `ptr`/`indices`/`lengths`/`areas` as inputs and write only `comp` and their
  scratch). So the year-invariant structure is now built once per group by `PatchGroupTopology` and
  shared through `PatchGroupYear.from_topology`, with the constructor unchanged for callers that hold
  a `neighbours` mapping; the topologies survive a `reset`, so a search pays once per group. Identical
  results: the parity and patch-model suites pass unchanged, and a new test runs a shared-topology
  state and a self-contained one through the same 120 mutations comparing every cell. Dashboard:
  **GREEN** (seven gates).
- P9.4 (performance, #101): **the curve gather, addressed flat — 1,133 -> 858 us (-24.3%) on a real
  C5 call, and the 30-year simulate -6.1%**, with the documented benchmark reporting
  `simulate_base_seconds` **0.100 s** against P8.2's 0.113 s. Measuring first moved the target: on the
  C5 simulate gather is **0.0368 s of 0.115 s**, in 30 calls of 205,942 queries, and the cost is not
  the `np.clip`/`iinfo` P8.3 named (0.26 ms) but numpy's two-array indexing (0.83 ms of the 1.15 ms
  call), which folds strides and checks bounds per element. `table.ravel()[rows * (age_max + 1) +
  clipped]` computes the same addresses for -24%. A/B evidence is both implementations alternating in
  one process. Semantics pinned by two new tests: the clamp at both ends on a curve whose ends differ,
  and that the result is a copy the table does not alias. The docs' measured-figures header also said
  5.0k/14k iterations/s at 8/32 islands, contradicting the scaling table lower down the same page; it
  now carries P8.4's recorded 6.0k/18.7k (5.7x/17.7x) and the 30-year simulate reads ~0.10 s.
  Dashboard: **GREEN** (seven gates).
- Phase 9 (Spatial performance and memory) is held **active** on `feature/p9-memory` with its four
  engineering tasks complete (P9.1-P9.4) and P9.5 outstanding, decided with the maintainer rather than
  deferring #95 a second time: it needs an export from a licensed Windows run of the reference, and the
  phase closes when it lands. The roadmap now says so, with what the export must contain and the command
  that consumes it. The packaged sample Monday's run depends on was re-verified rather than assumed:
  `c5-sample-for-parity.zip`, 88 MB, sha256 `cd0aa1f3…`, extracted and checked against its 139 per-file
  digests, all OK. Dashboard: **GREEN** (seven gates).
- Rehearsed the accounts comparison end to end without a reference, and found a defect in it. The check
  derived the replay horizon from the schedule's last period, so a reference that reports years its last
  decision does not reach had every one of them reported as "only in the reference" — a spurious
  failure. It now replays the horizon the reference's own last reported year sets, and a schedule that
  decides *beyond* the reported years is reported as a difference in so many words. No test had seen it
  because the test helper derived the horizon the same wrong way the check did; two new tests cover
  both directions, and the existing self-agreement test is unchanged. Rehearsed with an export written
  from WS4's own simulate on the C5 sample (300 blocks, 113 account-year cells): it **passes**, and a
  copy with one value multiplied by 1.5 **fails** naming that cell. The rehearsal exports and a
  one-command runner are beside the workspace as `PARITY.md` + `parity-run.sh`, with the packaged sample
  pre-compiled, so the Windows export is the only thing missing. Dashboard: **GREEN** (seven gates).
- P9.6 (maintenance, #102): put the package under the strict type gate. `[tool.mypy] files` now names
  `ws4`, so the `types` gate checks **93 files where it checked 50**; `mypy` reports **success** with no
  fixes needed, which closes the backlog item that had been open since the P5 triage — the work behind it
  was already done, and only the file list was missing. Also closed the backlog item for P7.5's lever,
  both halves of which the phase has now taken (the series 29% cheaper in P8.3, the patch-state
  construction 89% cheaper in P9.3, with state laziness rejected for P8.3's recorded reason). Dashboard:
  **GREEN** (seven gates).
- P9.6 closed (#102): the type gate has been widened in the changelog entry above and the roadmap now
  ticks it. Dashboard: **GREEN** (seven gates).
- Recorded the work requested while the P9.5 export is pending: the growth-parity check (#103) next, then
  an API-first notebook for the examples gallery (all seven are currently CLI-first) and capability work
  from the backlog's `partial` items. The last two are outside P9's subject, so the roadmap lists them as
  planned work for their own phase rather than folding them into this one.
- P9.7 (verification, #103): **growth checked against the reference's own yields, without a licensed
  reference run** — `scripts/acceptance.py` gains a `growth` check (`--yield-sample`, `--yield-dataset`)
  that resolves each of the sample's 18 `Y<n>.Conif/Decid` curves to the compiled curve reproducing its
  ages and compares every point at 5e-3 (the reference's artefacts print two decimals). On the C5 sample:
  **"WS4 reproduces the reference's 959 yield-curve points, with 7 recorded upstream conflict(s)"** — no
  missing ages, every value agreeing but one. The conflict is the sample's, not WS4's: at offset age 7
  the Decid curve is **0.001 in the legacy matrix** WS4 ingests (`tracks/curves.csv`, nine rows) and
  **0.01 in the same sample's own** `C5_yld.prn` and `ForestModel_C5_strata.xml`, and the matrix holds no
  0.01 anywhere. It is recorded by name rather than absorbed into the tolerance, so another curve
  differing at that age still fails; six tests cover pass, a changed value, a missing age, the recorded
  conflict, a conflict outside it, and the skip. Dashboard: **GREEN** (seven gates).
- Launched Phase 10 (Documentation and the API-first workflow): parent issue #104, branch
  `feature/p10-docs-api`, and three tasks — an API-first walkthrough notebook for the gallery (#105),
  a check that executes the notebooks and reports drifted output (#106, since the gallery's outputs are
  committed with `nbsphinx_execute = "never"` and nothing verifies them), and naming which way in each
  example takes (#107). Phase 9 stays open only for P9.5 (the accounts export); its other six tasks are
  complete. The roadmap records the backlog's capability work as the phase after this one.
- Fixed the Phase 10 launch commit: the roadmap tracker row I wrote for P9 said "active (held on the
  P9.5 export)" where the phase section says `active`, and the workflow validator caught the mismatch on
  the next run — the launch commit had landed while the dashboard was red because the command chain ran
  on regardless of the exit status. The tracker row is back to `active`, the holding note stays in the
  phase section where it belongs, and the dashboard is **GREEN** (seven gates) again. Third time this
  session a chained command hid an exit status; the chain is the problem, not the tool.
- P10.1 (docs, #105): **an API-first walkthrough notebook**, `examples/070_library_path.ipynb`, executed
  and in the gallery. Five of the seven existing examples drive the command line, so the library
  audience had prose but no worked session; this one runs no `ws4` command anywhere — it compiles the
  sample estate, opens it with `Model`, simulates two schedules in memory and compares them, runs a
  search through `Optimizer.run`, reads the target table and the account values back as frames, and
  checks the run's own numbers against a fresh simulation (largest difference 2.3e-13). Linked from
  `getting-started/python-api` and `howto/automate-a-study`.
- P10.3 (docs, #107): every example now says which way in it takes — command line, library, or both — in
  its own opening paragraph, and the gallery's intro explains the distinction, with `070_library_path`
  named as the counterpart to `010_quickstart`.
- P10.4 (fix, #108): **`report_targets.csv` priced a periodic target from one year.** Found by the
  notebook above, whose output showed the search returning `incumbent_objective 0.0` while the report
  said `below`: on the sample estate the target's period totals **5,549.86** over years 0-9 where the
  report read the year-0 row alone, **1,627.14**, and charged a penalty of 3,372.86 the search never
  applied. `target_status` now sums the account over `target.cell_years()` — the same expression the
  objective uses — so a target with `period_width > 1` is reported as the search priced it. Three new
  tests, including one that asserts the report's total penalty equals `objective`'s for the same values.
  **Recorded rather than fixed, and checked as the task required:** targets with `flow` set are still
  mis-reported, because `target_status` has no notion of a flow series at all — measured, an `ndy`
  target with `minimum: -1` over a series dropping 100 -> 60 is priced at **39.00** by the objective and
  reported as `met` with **0.00**. Left open in `notes/backlog.md` with those numbers, because fixing it
  means deciding what the report should show for a flow target. Dashboard: **GREEN** (seven gates).
- P10.2 (verification, #106): **the gallery's outputs are now checked, not trusted.**
  `scripts/check_notebooks.py` re-runs every example in memory and compares what it produces with what is
  committed, cell by cell, naming the notebook and the cell when they differ and writing nothing; the
  remedy is the documented `--refresh`, which re-runs and rewrites. It took **8 minutes** on the eight
  notebooks, so it is its own CI job rather than part of the dashboard, and it is honest about what it
  cannot compare: the environment's version banner, durations, rates, memory and absolute paths are
  normalised and **counted** (a passing run reports `duration x2, elapsed x2, rate x2, version x10`),
  and cells whose output is a live render can be tagged `no-drift-check` in the notebook itself.
  Its first run over the eight notebooks: **5 drifted**, and the first catch was this phase's own work —
  four of them (030, 040, 050, 060) because the P10.4 fix corrected the target values their report tables
  print (`060`'s `volume_share` 18,744.60 -> 36,352.44), and 010 because a `ws4 watch` progress table
  prints an elapsed time; the four were refreshed and committed, the fifth masked. The suite now reports
  **50 cells compared, 0 skipped, 0 drifted**. Seven tests cover a current notebook, a stale one, a
  tagged cell, the normalisations, a notebook that no longer runs, the per-cell outcome, and the refresh.
  Dashboard: **GREEN** (seven gates).
- Queued the Phase 10 close-out: the report is `notes/reports/p10-closeout.md` and the roadmap moves P10
  to `pr-open`. The pull request is **stacked on `feature/p9-memory`**, because P10 was branched from it
  and Phase 9 is held open for the P9.5 export: a pull request against `main` would carry P9's unmerged
  work as well, so the stack shows P10's own four commits and the base can be changed with one command
  if the maintainer would rather land both at once.
- Fixed what the Phase 10 pull request's first CI run found, on two jobs. The `Notebook outputs` job
  reported `000_environment_check` drifted because its banner cell says whether `geopandas` is
  importable — the environment, not the code — so that cell, the optional-dependency cell and the
  rendered `ws4 --help` screen are tagged `no-drift-check` **in the notebook**, which is what the tag
  exists for; the notebook now reports `3 compared, 3 skipped, 0 drifted`. The check's own tests failed
  in CI because the notebooks they build carried no kernelspec, where the committed notebooks do, so the
  fixture now sets the same metadata. Both deviations are in the close-out report, and the dashboard is
  **GREEN** again.
- Fixed the second CI failure on the Phase 10 pull request: the check's tests need a kernel, and the
  gate jobs had `nbclient` (through `nbsphinx`) but not `ipykernel`, which is what ships the `python3`
  kernel spec, so they failed with `NoSuchKernel` while the `Notebook outputs` job passed — it installs
  both explicitly. `requirements-dev.txt` now names `nbclient` and `ipykernel` with the reason, so the
  suite carries what it needs rather than depending on a transitive dependency. The `Notebook outputs`
  job itself is **green in CI**; dashboard **GREEN**.
- Third CI iteration on the Phase 10 pull request, and a correction to the check's doctrine rather than
  a workaround: the `ws4 watch` progress table drifted in CI by **one column of padding**. A rich table
  is drawn to the width of its values, so masking the values is not enough — the check now flattens
  layout too, removing box-drawing characters and column padding and **counting** them (`layout x5706`
  on a full run, alongside `duration x2, elapsed x2, rate x2, version x10`). Content is still compared
  exactly; the width it was rendered at is not. A unit test pins two differently-padded renders of the
  same content as equal. Locally the suite reports **47 cells compared, 3 skipped, 0 drifted**;
  dashboard **GREEN**.
- **Phase 10's pull request is green in CI**: run `39104469800` on `9bcdcfd`, all four jobs — Quality
  gates, Green dashboard summary, Pre-commit parity, and **Notebook outputs**, the new job whose first
  outings found the three defects recorded above. The close-out report now carries the four runs in its
  CI evidence table, including the three failures and what each one turned out to be. The pull request is
  queued for the maintainer's approval.
- Carried out the Phase 10 close-out: pull request #109 squash-merged as `b512cd9`, the branch deleted,
  and parent issue #104 closed. It merged into `feature/p9-memory` rather than `main` because it was
  stacked there; the conflict with Phase 9's later work (P9.5 and P9.8 touch the roadmap, the changelog,
  the backlog and the acceptance checks) was resolved by keeping both sides, with the workflow validator
  and the seven-gate dashboard green on the merged tree and CI green on all four jobs. Phase 10 is what
  the enclosure found: the library-path notebook the gallery was missing, **`scripts/check_notebooks.py`**
  re-running every example and reporting drifted output, labels naming each example's path, and the fix
  for `report_targets.csv` pricing a periodic target from a single year. Dashboard: **GREEN**.
- Queued the Phase 9 close-out: the report is `notes/reports/p9-closeout.md`, the roadmap moves P9 to
  `pr-open`, and its pull request is against `main` carrying Phase 10 with it, since Phase 10 was
  stacked on this branch and merged into it (`b512cd9`). The report's recommendation is the derived
  targets — the reference's ratios, flow constraints and patch-size distributions, 178 of them — and the
  three sample-side gaps this phase uncovered: WS4's period convention against the reference's, the
  sample's two-mill set, and the growth check's retargeting.
- Carried out the Phase 9 close-out: pull request #111 squash-merged as `e48c308`, the branch
  `feature/p9-memory` deleted, and parent issue #97 closed. As approved, it landed **with Phase 10**,
  which had been stacked on that branch and merged into it (`b512cd9`), so the two phases reached `main`
  together. Its evidence is the accounts comparison passing on both 2026 scenarios (1,323 account-period
  values each) and the matrix-builder defect it found, the shared-dataset attempt measured and reverted,
  island scaling reproducing P8.4, the patch-state construction 89% cheaper, the curve gather 24%
  cheaper, and the type gate widened to the package. **Launched Phase 11 (The derived targets and the
  sample's own files)**: parent issue #112, branch `feature/p11-derived-targets`, six tasks — the period
  convention (#113), the ratios (#114), the flow constraints (#115), the patch size and age-class
  distributions (#116), the routing check's mill set (#117), and the growth check's retargeting (#118).
  Dashboard: **GREEN**.
- P11.1 (parity, #113): **WS4's period convention now matches the reference's.** A target names the year
  its period **ends** on, and it accumulates only if it is a `product.` account; everything else — a
  feature, a patch, a share — is a level read at that year. Pinned from the reference's own period
  values, not inferred: an account it reports as **1,921,975.8** for year 10 is the sum of WS4's years
  1-10 (**1,921,975.7**), where the old start-labelled window summed years 10-19 (1,461,044.0), and its
  `feature.Area.managed.PL` at year 10 is the level (38,436.2) where WS4 summed ten years of it
  (384,362.3 — **ten times high**). The objective, the report, the incremental evaluator, the patch
  accounting points and the MIP bound all follow one rule, `ws4.opt.objective.accumulates`, and the
  docs that described the old mapping are corrected — including the ones that already said period 0 is
  the snapshot while the code's window disagreed. The acceptance comparison still passes on both 2026
  scenarios, **1,323 account-period values each**. Dashboard: **GREEN**.
- Refreshed the example notebooks after P11.1's period-convention change: **13 cells** across five
  notebooks had genuinely drifted, because a level's accounting year moved from its period's start to
  its end — the sample estate's patch targets are levels, so their searches now price differently (070
  schedules 19 blocks where it committed 8; 060's sweep values moved). The remedy is the documented one:
  `python scripts/check_notebooks.py --refresh`, then a re-check, which now reports **47 cells compared,
  3 skipped, 0 drifted**. Recorded rather than silently regenerated: the outputs changed because a
  convention changed, and the check is what caught it.
- P11.2 (#114): recorded what the reference's ratios divide by — read from its own `addRatioAccount` and
  `addMetaAccount` calls in `analysis/C5.pin` — and, comparing WS4's route cost report against the
  reference's own `route/routeCostMILL*.csv`, that they cannot be compared honestly yet: the two reports
  are **the same table** but WS4's maintenance is **~100×** the reference's, its reported window is a
  year against the reference's ten, and its routed volume is every product where the reference's mill
  product is the conifer share. Handed to #117, which is the same subject and the same report. Dashboard:
  **GREEN**.
- P11.3 (#115), in progress: the flow targets' **windows and reporting**. `flow_values` still built its
  periods start-labelled — a convention P11.1's sweep had not reached — and with the periods ending at
  their year WS4 reproduces the reference's own flow values to four decimals (period 1: **40.244** both
  sides; period 4: −4.435 both). `report_targets.csv` no longer prices a flow target as a level: it
  emits **one row per period** of the series, priced by the same `penalty` the objective uses, which
  closes the reporting gap recorded in `notes/backlog.md`. `flow_period_ends()` exposes the period grid
  the series belongs to, and twelve flow tests now state the end-labelled convention. What remains is
  mapping the series onto the reference's rows — an `even` series omits its reference period — and the
  comparison, which belongs with the other derived targets. Dashboard: **GREEN**.
- P11.3 (parity, #115): **the flow constraints compared, and the report bug closed.** The reference's
  flow definitions come from its own model file: `ndy(periods-9, periods, -1)` over the last ten periods
  for the two growing-stock features, `even()` over the horizon for the products. Three things had to be
  right, and the first two were the period convention reaching paths P11.1 had missed: `flow_values`
  built **start-labelled** periods, and it **summed every account** over each period where a flow on a
  growing stock is a *level* read at the period's end — the same accumulate/level rule as a target's
  value. With both fixed, WS4's flow values match the reference's own `targets/flow_*.csv` to four
  decimals (period 1 at 40.244 on both sides). A third: where a flow's balance is empty the reference
  reports **0.0** (satisfied) while WS4 priced it infinite; reports and comparisons now carry the
  reference's reading, and the pricing question is in the backlog with the measurement. And the bug
  itself: `report_targets.csv` priced a flow target as a level, so a flow target could be reported as met
  while the search paid for it. It now reports **one row per period**, priced by the same `penalty` the
  objective uses. The acceptance comparison covers the flows alongside the accounts: **1,383
  account-period and flow values reproduced on both 2026 scenarios**, with the families it cannot yet
  compare named — 2 per-mill allocations, 63 patch distributions, 52 ratios. Dashboard: **GREEN**.
- P11.4 (#116), first measurement: **the patch comparison runs and disagrees.** WS4 can express the
  reference's `patch.young` family today (a patch account over `feature.young`, classes 0-50 to
  2500-plus, topology at a 100 m distance), and over 16 cells × 21 periods its **areas, sizes and
  frequencies are within 10-20%** of the reference's own `targets/patch_young_*.csv` — the same order, so
  the patches are formed and classed comparably and the difference is systematic rather than random —
  while its **`shape` is 0.2x to 12.4x** off, which is a definitional difference (WS4 reports
  compactness 0-100, the reference another quantity) and needs pinning from the reference's numbers
  before anything is changed. Three of the reference's seven sub-quantities have no WS4 counterpart
  (`blocks`, `freqpercent`, `attractor`), the open-ended class is labelled `2500_plus` by the reference
  and `2500_9999999` by WS4, and **the harvested family cannot be configured at all** because its
  criterion is `product.harvested` — a product, not a feature — which is 28 of the 63 targets. Recorded
  on the issue with the next subtasks. Dashboard: **GREEN**.
- P11.4 (#116), the gap measured: the patch family is **not** off by a scale. Over the periods, WS4's total
  young-patch **area is 0.92** of the reference's, its **patch count 1.03** and its **mean patch size
  0.96** — the aggregate structure is within about 8%, so the two agree on how much young forest there is
  and how it is broken up, and the per-class differences are the distribution moving rather than a
  misplaced definition. Individually the cells are not close: 5.7% within 1e-4, 28% within 10%, 50%
  within 20%; `area` differs by a median 14%, `frequency` 9%, `size` 18% and `shape` 83% (a different
  quantity on a different scale). The next question is which patches **form** in which period, which is a
  comparison of the components rather than of their sums per class. Recorded on the issue. Dashboard:
  **GREEN**.
- P11.4 (#116), the sub-accounts: the reference's own documentation for its patch sub-accounts corrected two
  readings and closed most of the gap. `blocks` is the **mean number of blocks a patch of the class
  holds** — which WS4 already held in its state and did not expose — and `freqpercent` is the class's
  share of all patches; both are now cells, computed from the class's own membership rather than a
  running total that a detach would make drift, and both are backed by the from-scratch oracle the parity
  tests check the incremental state against. `shape` is **the same definition** WS4 already has (its
  compactness is the inverse square), so the difference is which patches form rather than the metric.
  The comparison now covers **630 cells over six quantities** (was 336 over four), 45% within 10%, with
  medians of 12% (`area`), 7% (`blocks`), 15% (`size`), 8% (`frequency`) and 3.5% (`freqpercent`). The
  five `attractor` cells are the only ones it cannot make: the reference reports values of its own for a
  sub-account WS4 has no counterpart for. What is left is the patches themselves — WS4's aggregate area is
  0.92 of the reference's, its count 1.03, its mean size 0.96 — so the components merge or split
  differently on the same schedule. 514 tests pass. Dashboard: **GREEN**.
- P11.5 (#117), the route accounting: **two fixes worth having.** The ledger charged each used segment's
  maintenance **per routed flow**, making maintenance a function of traffic — conceptually defensible and
  not what the reference does, which charges each used road once for the period. Measured on the 2026
  sample it was about **170×** the reference's per-period figure; with the reference's reading, WS4's
  maintenance is **1.12** of the reference's and its haul expense 1.05, its built length 1.01 (over the
  compared periods). The ledger's own test pins it: nine times the volume over the same segments leaves
  the maintenance unchanged and grows only the haul, and it fails against the old behaviour (checked by
  stashing the fix). The routing parity check also now compares the quantity the reference's table
  *holds* — the 2026 sample ships `SUM_LENGTH` where earlier samples shipped `SUM_HAUL` — and skips a
  reference table for a destination the model does not declare, naming it rather than reporting it as a
  difference. With both, the 2026 sample's routing disagreement is a real one and precisely stated: **10
  of 25,134 node-and-mill pairs**, where WS4's route is 97,169 m against the reference's 81,098 m. The
  maintainer's direction is recorded in the roadmap: **verified parity first**, deliberate divergence
  after, with a parity mode as the home for it — and the traffic-weighted maintenance is in the backlog
  as the first candidate for that divergence. Dashboard: **GREEN**.
- P11.5 (#117), the routing question: **WS4 now agrees with the reference on all 25,134 routed
  node-and-mill pairs** of the 2026 sample. The ten remaining "differences" were not routing errors: the
  2026 sample's table holds `SUM_LENGTH` where the 2019 sample's held `SUM_HAUL`, and for those nodes the
  reference's value is the **shortest path by distance** (81,098 m) where WS4's least-haul route is
  97,169 m — measured by weighting the same network three ways, the length-only optimum reproduces the
  reference's number exactly, while optimising haul or haul-plus-build does not. So the table asks "how
  far is this node from the mill" and the like-for-like comparison is WS4's own shortest distance; the
  check now uses `RouteNetwork.route_length` for a distance table, the haul sum for a cost table, and
  skips a table for a destination the model does not declare, naming it. Two tests pin both branches.
  The phase's general lesson, recorded in the parity note: when a comparison disagrees, ask first whether
  the two sides are being asked the same thing — three of this phase's largest differences (the period
  convention, the patch `shape` metric, and this) were that rather than a defect. Dashboard: **GREEN**.
- P11.5 (#117) / P11.2 (#114): **a route account can name the product whose volume it tracks**, so the
  reference's mill products are expressible as they mean them — a volume account for one product at one
  destination. Two tests pin it: the filtered account sums only that product, and a *cost* account naming
  a product is refused rather than ignored. Pointing it at the reference exposed the next question rather
  than closing it: WS4 routes **24,349** of `product.Yield.managed.Conif` to Mill 1 where the reference
  reports **1,029,670**, while WS4's all-product volume is 1.6× the reference's — so the difference is
  *attribution*, not quantity. The reference allocates the conifer yield between the two mills as an
  exclusive account and duplicates each share into its destination, where WS4 routes each block by
  least cost; that allocation is what #114's route ratios wait on. Recorded in the parity note.
  Dashboard: **GREEN**.
- P11.2 (#114) closed, with the capability #117 was missing: **a destination allocation**, which
  partitions a master product across the destinations it is routed to with an account for the
  remainder — the reference's own shape for its mill products. It partitions exactly (Mill 1 plus Mill 2
  equals the master's own value, nothing unallocated on this sample), refuses shares that exceed their
  master, and is tested both ways. Pointing it at the conifer yield made the remaining difference
  legible and it is a **modelling** difference, not a comparison one: WS4 sends each block's product to
  its cheapest mill (118,498 / **251,703**), where the reference's near-balanced 54/46 (1,029,670 /
  892,306) comes from its own exclusive-account allocation under mill minimums. So the route ratios'
  denominator is a quantity the two tools decide by different rules; comparing the ratio needs the
  reference's destination policy first, which is its own task. The ratio definitions, the coverage and
  that blocker are all recorded, and the acceptance check names the 52 ratio targets it leaves out and
  why. One correction kept: the first run doubled the mill volumes because the configuration had both a
  volume account and an allocation writing the same name — caught by the master guard, once it checked
  every year either side knows. Dashboard: **GREEN**.
- P11.6 (#118): **the growth check retargeted for the 2026 sample**, which states its yields as one
  `<curvetable>` — an age column and a column per curve, `Y1.Conif` through `Y9.Decid` — where the 2019
  sample states a `<curve>` element per stratum and species. The check reads both shapes, so the same
  comparison runs on either vintage, and on the 2026 sample it reports **959 yield-curve points
  reproduced** across all eighteen curves. Recorded with it: the 2019 sample's conflict (its matrix
  holding `0.001` at offset age 7 on the Decid curve where its own artefacts held `0.01`) is **absent
  from the 2026 data** — 1,399 curves carry `0.01` there and none carries the other value — so that
  conflict was a property of the 2019 sample's files rather than of the model. Two tests cover the table
  shape, one for agreement and one for a value that disagrees. Dashboard: **GREEN**.
- P11.4 (#116) closed: **the patch family measured, its sub-accounts closed, and the two places the
  comparison stops measured rather than assumed.** It covers 630 cells over six quantities (area, blocks,
  size, shape, frequency, freqpercent) with medians of 12 / 7 / 15 / 8 / 3.5 percent against the
  reference's own `targets/patch_young_*.csv`. The stops: **the harvested family cannot be configured**
  (28 of the reference's 63 patch targets — its criterion is `product.harvested`, a product, and WS4's
  patch state evaluates a criterion as a feature, so the account is accepted, runs, and produces every
  cell zero, which is a silence worth refusing rather than a comparison fix); and **the components are
  not in the export** (the reference publishes class aggregates and map images, not patch membership), so
  what the aggregates say is what can be said: WS4's young-patch area is 0.92 of the reference's, its
  count 1.03, its mean size 0.96 — the structure within about 8% — while individual cells differ by a
  median 9-18%. Both stops are in the backlog as capabilities. Dashboard: **GREEN**.
- Queued the Phase 11 close-out: the report is `notes/reports/p11-closeout.md` and the roadmap moves P11
  to `pr-open`, its pull request against `main` (the branch was cut from `main` after Phase 9 and 10
  landed, so nothing is stacked). The report's recommendation is **P12 (Spatial decision match)**: a
  patch criterion that can be a product (28 of the reference's 63 patch targets), the reference's
  destination policy for its mill products (which the route ratios wait on), the route report's
  period width, the `attractor` sub-account, a **Patchworks-parity mode** with traffic-weighted
  maintenance behind it, and a patch-component comparison carried on a new reference export.
- Refreshed the example notebooks for the phase's own fixes, and recorded why rather than regenerating them
  quietly: **020_even_flow**'s series changed because a flow target now means what it should — a level is
  not summed over its window and a period ends at its year — so that notebook's search genuinely behaves
  differently; and **050_routes_and_mills**' maintenance column changed because maintenance is charged
  once per used road rather than per routed flow. Both were caught by the notebook drift check in CI, the
  remedy is the documented `--refresh`, and the re-check reports **47 cells compared, 3 skipped, 0
  drifted**.
- Carried out the Phase 11 close-out: pull request #119 squash-merged as `0d34412`, the branch
  `feature/p11-derived-targets` deleted, and parent issue #112 closed. The close-out report is
  `notes/reports/p11-closeout.md`; its acceptance evidence is the period convention matched to the
  reference's, the flow constraints and their reporting bug, routing parity on all 25,134 node-and-mill
  pairs, a patch family compared over 630 cells, and the growth check reading either vintage's shape —
  along with two WS4 defects fixed on the way (the matrix builder's track attribution and road
  maintenance charged per routed flow). **Launched Phase 12 (Spatial decision match)**: parent issue #120,
  branch `feature/p12-spatial-decisions`, six tasks — a patch criterion that can be a product (#121), the
  reference's destination policy for mill products (#122), the route report over the model's periods
  (#123), the attractor sub-account (#124), a Patchworks-parity mode with traffic-weighted maintenance
  behind it (#125), and a patch-component comparison carried on a new reference export (#126). Dashboard:
  **GREEN**.
- P12.1 (#121) closed by **refusal, with the reason measured.** The reference's harvested patches name
  `product.harvested` as their criterion and WS4's patch state evaluated a criterion as a feature, so the
  account ran and returned **every cell zero**. The lookup was not the problem: keying it by
  `(track, treatment, label)` rather than `(track, label)` made the series non-zero, but its values landed
  at the **wrong time** — a block the schedule harvests in year 44 had its product's value appear in year
  **150**, because a product's curve read against a fragment's age is not the product of the treatment
  that happened. A wrong value that looks right is worse than a zero that looks like a zero, so the
  product path is **reverted** and the criterion is **refused** with the reason, as is a label that is
  neither a feature nor a product. Two tests cover both refusals; the feature path is unchanged. The real
  fix — the product evaluated on the treatment's own timeline — is in `notes/backlog.md` with this
  measurement. Dashboard: **GREEN**.
- P12.2 (#122) **the destination decisions are compared, and the mill products with them.** The
  reference's rule is established from its own model file and its exported decisions:
  `addExclusiveAccount` divides each master product, so conifer may reach either mill while **deciduous
  may reach Mill 2 only**. WS4 had been sending **62.7% of the deciduous area** to a mill the reference
  never uses — an error rather than a policy difference — and with the eligibility declared
  `product.Mill2.Yield.Decid` agrees with the reference to **4 units in 2.78 million**. WS4's rule is
  the reference's declared destinations and then the least haul cost, which reproduces the reference's
  own choice on **12,266 of 13,377 conifer block-periods (91.7%)** and on **13,375 of 13,377 deciduous**
  ones. What is left is the reference's **delivery target** — Mill 1 held at 800,000 a period with Mill 2
  taking the remainder, which is the whole of the difference (+8.1% / −13.3% over the horizon) — a
  planning decision that changes where wood goes, so it is recorded for the parity mode rather than
  adopted as WS4's only behaviour. The surplus account is now declarable **per product**, as the
  reference declares it, and a new `destinations` acceptance check reads the splits from
  `analysis/C5.pin`, compares the decision block-period by block-period and the mill products period by
  period, requires what the model's own split forces and measures what it leaves free. The stale note
  that compared one of WS4's *years* against one of the reference's *periods* is corrected. Dashboard:
  **GREEN**.
- P12.3 (#123) **the route cost report is folded into the model's periods, and the model's period
  width now reaches it.** `period_width` was a route-configuration setting that nothing used; it is
  wired through `Simulator.run` to the ledger, and a period is labelled by the year it ends at and
  carries that width, as the reference labels its own. The extensive columns are summed over the period's
  years and the averages recomputed from those sums — the reference's own arithmetic — and a width of one
  leaves the report exactly as it was, so nothing older moved. The report is **per destination** as well
  now, which is how the reference ships it, and writing it that way exposed a real defect: the
  per-destination state recorded a segment's build expense and never its built length. Compared over the
  twenty periods of the base scenario, three of the differences are explained: `VOLUME` is now the same
  quantity on both sides (8% and 10% apart, which is #122's destination policy) because a map that names
  products is now also what is *delivered* — WS4 had been routing **27 products** to the mills beside the
  yield, areas and volume classes among them, and 2.26× the reference's volume was the symptom;
  `AVERAGEHAULDIST` is a **unit** (WS4 counts metres, the reference kilometres, so 1.2× reads as 1,200×);
  and `BUILTLENGTH` was the defect above. One quantity is left unexplained and recorded as such: what the
  reference's `LENGTH` counts, where WS4 is 2.6× and 3.3× and maintenance is consistent with it on both
  sides. Dashboard: **GREEN**; acceptance **PASS**, `destinations` and `accounts` included.
- P12.4 (#124) **the patch `attractor` sub-account is established, and refused rather than faked.**
  WS4 wrote a `1.0` flag for it whenever an account declared one. From the reference's own 360 values
  across both scenarios and all eight classes, what it reports is a **per-class landscape quantity**: zero
  in exactly the cells where the class holds no patches, and otherwise a lower quantile of the class's
  patch sizes — within one class a stable 0.52 to 0.69 of the class's mean patch area, falling to 0.015 in
  the largest. It is **not** the class's mean patch size (a class bounded below by 50 reports 15.7),
  **not** its `size` share (the ratio runs 0.26 to 2.57 cell by cell, which contradicts the reading the
  documentation invites), and **not** a function of the six sub-accounts the export publishes (a
  log-linear fit leaves a 9% median and a 58% worst residual). Its target carries the class's size range
  and 278 of 360 values sit outside it with a `SUMMARY` of 0, so the reference's own report does not
  evaluate it as an objective term. So the flag and its field are **removed**, and an `attractor` setting
  is **refused** with that reason, as the product patch criterion is — the same export that leaves the
  patch components incomparable (#126) is what would make it computable. No shipped configuration asked
  for one. Dashboard: **GREEN**.
- P12.5 (#125) **parity is the default, and the one divergence WS4 offers is named rather than
  implicit.** A route configuration's `divergences` block declares what WS4 computes *differently*, one
  named entry per quantity; everything else is the reference's reading, an unknown entry is refused
  rather than ignored, and so is a maintenance reading WS4 does not have. The first entry is
  **traffic-weighted maintenance**: the reference charges each used road once a period (`f(0) = 0`,
  `f(x > 0) = b`), and WS4 offers the affine form the maintainer specified — `b + a·x` — with the
  reference's reading as the `a = 0` default. Its effect is **measured** on the 2026 base scenario
  replayed: the maintenance is +4.2% of parity at `a = 0.001`, +42.4% at 0.01 and ×5.24 at 0.1, with the
  haul unchanged in all four runs. Two defects came out of making it a reading: maintenance was charged
  once per *produced product* in the route accounts while the report charged it once per segment per
  period (**7.0×** apart on MILL 1 — now 1.0000, both through one charge computed after every flow of the
  period is in), and the optimizer's incremental path now **defers to the full simulation** when a
  configured route account is `build` or `maintain`, which are charged per segment and cannot be a
  per-block sum. Dashboard: **GREEN**; acceptance **PASS**; 551 tests; examples 0 drifted.
- P12.6 (#126) **the patch component comparison is built and tested, and the class aggregates are
  recorded as the ceiling.** WS4 can now state its own components — `patch_membership.csv`, one row per
  member block of every patch, written beside `patch_accounts.csv` on a run — and
  `compare_patch_components` compares two listings over their **partitions** rather than their labels:
  two listings agree on a period when every patch on one side is exactly a patch on the other, and a
  patch spanning more than one on the other side is reported as a merge with an example and the block
  counts. It is tested against a listing with a **known** difference, so it can fail, and the new
  `patchcomponents` acceptance check runs it against a listing under the export's `patch` directory. The
  reference cannot supply one: every report group of the 2026 export was read — `patch/` holds four
  *Target table* reports (the class sub-accounts in another shape), `harvest/maps/` is `MapReport`
  images, `nta/` is aggregates, `scenario/` holds block attributes and no patch attribute — and the
  maintainer has confirmed the export is everything Patchworks can produce. So the check **skips with
  that reason on every run**, which is the honest statement of the ceiling, and the listing's
  specification is in `notes/design/ws4-parity-harness.md`. Dashboard: **GREEN**.
- P13.1 (#129) **the product patch criterion's mechanism is established and implemented, and the
  harvested family is compared for the first time.** A product's curve is not a level: the legacy
  `products.csv` states `TRACK,TREATMENT,LABEL,FUTURE,ADJUST,METHOD,CURVE`, the track is the track the
  treatment is applied *on* (all 1,248 tracks the harvested product is stated on are CC-treatment
  tracks), the curve is a **window over that track's age** (curve 91 is 1.0 on ages 150–424 and 570–844 —
  the CC window the treatments table states), and `FUTURE` is 0, so the product is produced **in the year
  of its treatment**. `block_criteria` and `block_criteria_series` now answer for a product as a **flow**
  normalised as a feature criterion is, from the same computation the product accounts use, kept as
  per-year state. The harvested family is compared and its **timing and shape are right** — a flow in the
  harvest year, nothing elsewhere — while the areas are **0.11 to 0.16×** the reference's over 0.11 to
  0.17× its patch count, so *which blocks qualify* differs; the criterion is refused again with that
  measurement and the unverified age-window explanation rather than reported. Dashboard: **GREEN**.
- P13.1 (#129, continued) **the harvested patch family is compared and agrees.** The criterion's
  mechanism is a flow — a product's curve is a window over the pre-treatment track's age, and what it
  yields is produced in the year of its treatment — and a criterion is that as a share of the **block**.
  Two further readings had to be right, each caught by measurement: dividing by the *treated* area
  instead of the block's put the family at **1.38×** the reference's area (the unmanaged fraction, to the
  third decimal), and the reference **sums its patch accounts within a period**, which its own field list
  states and which the harness now does too. With both, WS4's harvested patch area is **0.92** of the
  reference's over the horizon and its patch count **1.48** — the young family's quality (0.92 and 1.03)
  and shape, aggregate agreeing and components differing. So the criterion is **accepted** and 28 of the
  reference's 63 patch targets are comparable. Dashboard: **GREEN**.
- P13.2 (#131) **the reference's delivery target is implemented, and measured not to close the mill
  split.** The reference declares its mill volumes as annual minima (`setMinimumAnnual(..., 80000)`,
  which its report states as 800,000 over a ten-year period), so a route configuration can now declare
  a `DeliveryTarget(destination, product, per_year)`, a run fills it each year from the blocks nearest
  that destination by haul cost, and a search defers to a full simulation when one is declared. Imposing
  it moved the split the **wrong way** — Mill 1's conifer from 16,617,632 (1.081 of the reference's) to
  18,613,128 (1.211) — because WS4's cost rule already sends more than the minimum, so a floor only adds.
  The reference's numbers are a search outcome under **soft bounds** (its Mill 2 reaches 892,306 against
  a declared maximum of 650,000 with no violation reported), and WS4's rule is already 91.7% of the way
  there; the mechanism stays as the capability the reference declares, with the measurement recorded.
  Dashboard: **GREEN**.
- P14.1 (#134) **an initial schedule built by construction, for aggregate targets under a ceiling.**
  `ws4/opt/seeding.py` ranks every candidate chain by the penalty it removes from the declared floors
  per unit of the declared ceilings, takes them in that order, and **skips any that would push a ceiling
  past its maximum** — so the seed is not worse than the schedule the search already rejects, which is
  what separates it from `warm_start` (every block's first chain, ceiling ignored). It reads the targets
  (`minimum` is a floor, `maximum` a ceiling), so it names no account, model or treatment, and it is
  offered as `OptimizeConfig.greedy_seed`, `Optimizer.greedy_schedule()`, and `--seed-greedy` on both
  `optimize` and `watch`. The evaluator's per-chain contribution is now public
  (`IncrementalObjective.contribution`) because that is what makes the ranking cheap; a configuration
  the evaluator cannot price — duplicate accounts, a build account, edge contrast — is **refused with its
  reason** rather than answered with a quiet empty schedule. Measured end to end through the CLI on a
  60-block synthetic instance with a 30-block floor and a 35-block ceiling: **unseeded 8,700 (penalty
  34,800, below) against seeded 50,750 (penalty 0, met), with the haul at 507,500 exactly on the
  ceiling.** The TSA23 instance is not on this machine, so its reproduction is left to the maintainer.
  Dashboard: **GREEN** (570 tests).
- P14.2 (#136) **`--time-limit` now does what it says.** It was declared on `OptimizeConfig`, exposed
  on `optimize` and `watch`, and read by nothing, so a run presented as time-bounded was bounded only by
  its iteration count. A `HH:MM:SS` limit is now parsed once when the search starts
  (`parse_time_limit`), shared as a `time.monotonic` deadline with every solver
  (`solve_sa`, `solve_sa_delta`, `solve_tabu`, `solve_ils`, each checking `expired` at the top of its
  loop), and reported in the run's summary as `time_limit_reached`. The clock starts in **both** paths
  that run a search: `search()` and the single-start path in `run()`, which does not go through it. A
  malformed or non-positive limit is **refused** rather than ignored, since being ignored is the defect.
  Measured through the CLI on the synthetic instance with `--iterations 1000000`: at
  `--time-limit 00:00:05` the run stops with `time_limit_reached: true` in 6.4 seconds (the bound is the
  *search*; the final simulation and report follow it), and at `--time-limit 01:00:00` it spends the
  budget in 7.5 seconds with `false`. Dashboard: **GREEN** (573 tests).
- P15.1 **a spread-connectivity account, and the synthetic oracle that the patch-size account
  cannot pass.** `ws4/spread/accounts.py` measures how far a fire could run through the untreated
  blocks: the topology is undirected and carries no bearings, so the account supplies a **bearing** (the
  wind) and a **tolerance cone**, orients each transmitting edge downwind, and computes three
  sub-accounts — `largest_component` (the area reachable from one ignition), `percolation_reach` (the
  mean reachable area over untreated blocks) and `edge_cut` (the share of downwind edges leaving the
  untreated set that the treatment stops) — plus `TOTAL.area` and `TOTAL.blocks`. The oracle is a
  seven-by-seven eight-neighbour lattice with the treatment as the middle **row** or the middle
  **column**, same area, one connected band either way: a patch-size account reports the **same** largest
  patch for both, while the connectivity account separates them **90 against 190 ha** (largest
  component), **42 against 94 ha** (percolation reach) and **20% against 12.5%** (edge cut). Three
  modelling errors were caught by that oracle and are recorded in the module: undirected reachability
  made a band along the wind look as good as one across it; a 90-degree cone makes the measure
  symmetric on a regular lattice and loses the signal; and a four-neighbour lattice lets a 60-degree
  cone select only northward edges, degenerating every compartment into a corridor. Dashboard: **GREEN**
  (578 tests). The TSA23 bridge oracle is not on this machine, so that reproduction is the maintainer's.
- P15.2 **the spread-connectivity account is wired into a run and the optimizer.** A run
  computes it per year from the topology and a block-coordinate table, adds it to `account_values.csv`
  and writes `spread_metrics.csv`; the optimizer prices it on the whole-schedule rail (the move-based
  evaluator declines, since a graph property of the landscape has no per-block delta) and folds the
  run's own CSV into `report_targets.csv`. Declarable as `--spread-accounts` (YAML) with
  `--block-coordinates` (CSV of `block,x,y`) on `optimize`, `watch` and `calibrate`, and as
  `OptimizeConfig.spread_accounts_path` / `block_coordinates_path` in the API. One design flaw was
  caught by the end-to-end test and is worth recording: the account derived its *untreated* set from
  the criterion mapping, which for a **product** criterion holds only the blocks that produced, so the
  landscape came out empty and every sub-account read zero. The landscape is now the blocks the bearing
  can be read for, and a block with no criterion value is untreated. Dashboard: **GREEN** (579 tests).
- P15.3 **the bridge instance replaced the account's definition, and the docs now say what it can
  and cannot measure.** The TSA23 bridge inputs were on the shared drive, so the test was run rather
  than left to the maintainer. The patch-size result reproduced exactly (`agree: False`, 40.2 / 23.1 /
  26.0% in the 400+ ha class), and the **directed** account that P15.1 pinned failed on the real
  instance: at bearing 225° and a 60° cone its `largest_component` was **3,390.6 ha for all three
  patterns** — a boundary corridor no treatment touches — and its `percolation_reach` **reversed** the
  ranking (barrier 44.6, clumped 44.3, random 43.0 ha), because a thin barrier only shortens the runs
  that cross it while scattered treatment shortens every run. The reading that does reproduce the fire
  ranking is the **undirected compartment** over the fast edges: largest **82,800 / 104,600 / 187,173
  ha** and area-weighted mean **25,675 / 31,604 / 46,419 ha** against **19,640 / 19,870 / 20,298 ha**
  burned. The account is redefined accordingly: `largest_component` is now the largest connected set of
  untreated blocks over the within-cone edges, `percolation_reach` is its area-weighted mean
  (`sum(area**2)/sum(area)`), and `edge_cut` is removed — it is dominated by treated-edge contact and
  scored random highest on the real map. The oracle no longer claims a direction: it pins that a
  **full-span** band (row or column) cuts the 490 ha lattice to 210 ha while a **partial** band leaves
  450 ha, that a 20° cone fragments the map into 70 ha columns, and that the patch account cannot rank
  the two full bands. The module, package and design notes record the failed directed reading and the
  bridge caveats: the fire side treats 177,088 ha of whole blocks against WS4's ~46,600 ha of managed
  fragments, the fire spread is 3% on one seed, and the ordering holds from a 60° to 90° cone while the
  magnitude depends on the percolation threshold. Documentation: a *Spread connectivity* section in
  `docs/reference/spatial.rst` with the API entries, `spread_metrics.csv` in
  `docs/reference/simulator.rst`, and the targeting section in `docs/reference/optimizer.rst`.
  Dashboard: **GREEN** (579 tests, 7 gates). The bridge's footprint mismatch and the 4× FT curve remain
  open for the maintainer (see `tmp/bridge-finding.md`).
- Docs workflow repair: `docs/examples/070_library_path.ipynb` declared its Pygments lexer as
  `ipython3`, an alias registered by the third-party `ipython_pygments_lexers` package that the Docs
  workflow does not install. The notebook has no IPython magics, so its `language_info.pygments_lexer`
  is now `python3`, a core Pygments lexer; the workflow's `-W` build no longer treats six unknown-lexer
  warnings as errors. The workflow had been red on `main` since `e48c308` (2026-10-18).
- P14 close-out: the instance criterion the phase deferred is measured on the TSA23 instance. With
  `--seed-greedy` the run reaches **penalty 0.00** at **$199,999,193** against the $200,000,000 ceiling
  (9,999.96 ha treated), where the unseeded run stops at **15,758.97**; the corrected five-year targets
  reach **0.00** too. Both seeded runs report `time_limit_reached: false`. The report is
  `notes/reports/p14-closeout.md`; the 4× curve it exposes is left to P16.2. Dashboard: **GREEN**.
- P16.2 **the product table cannot multiply an account, and the simulator names a dataset that lets
  it.** The 4× `product.Treated.managed.FT` was not a 4.0 curve — its curve is the single point
  `(0, 1.0)`. It is a repeated product row: `compiled_ft/products.parquet` has **4,947,045 rows
  against 3,431,580 distinct `(track_id, treatment, label, curve_id)` keys**, so 1,515,465 rows are
  exact duplicates, and the key `(16, FT, product.Treated.managed.FT)` appears four times. The
  simulator records every row once per treated fragment, so the produced area read **186,568.7 ha
  against 46,642.2** with the repeats dropped — exactly 4.0000×. A repeated key is not always a
  defect: 85,532 keys carry different curves, the per-AU components of the `HarvestedVolume`, `Yield`
  and `SpeciesProp` families, and those are a sum. The builder now drops only rows identical in key
  *and* curve (`ws4.model.checks.unique_product_rows`), and `Simulator.from_dataset` warns with the
  count and affected labels for a dataset compiled before the rule; it also warns when an area-shaped
  product's curve exceeds 1.0. The earlier "the curve is 4.0" finding was wrong and is corrected in
  the untracked notes. Tests: `tests/test_dataset_checks.py` (six cases, including a recipe that
  declares the same product twice and a dataset that repeats a row). Dashboard: **GREEN**.
- P16.1 **the bridge ranking does not survive a matched footprint, and the compartment's validation is
  withdrawn.** Reusing the instance's own fire model (50 ignitions, 480 min, wind 225°, **ROS × 0.3** —
  the setting that produced the published JSONs, confirmed by reproducing `19640.448328143004` exactly
  with the original mask), the three patterns were rerun on the WS4-treated masks with the duplicate
  product rows dropped: **54,368 / 55,837 / 53,697 ha**, about 5.5% of the 988,816 ha model, against
  17.9% for the published patterns, five seeds each. The published ranking (barrier 19,640 < clumped
  19,870 < random 20,298 ha) does not hold: seeds 1–2 order barrier, clumped, random; seeds 3–4 order
  clumped, random, barrier; seed 5 orders barrier, random, clumped. Over the seeds the mean ranks
  **clumped 22,775 < random 22,816 < barrier 22,861 ha**, the reverse of the published order, with a
  largest mean gap of **86 ha (0.38%)** against a seed-to-seed range of **~3,400 ha (15%)**; the p90
  orders the same way. So the arrangement effect at 5.5% treatment is inside noise, and P15's claim that
  the compartment reproduces the ranking — made against a 3.3× larger fire-side footprint — is
  withdrawn. The account remains a defined fragmentation metric; its fire-response validation does not
  hold. Report: `notes/reports/p16-bridge-matched.md`; the thesis-side independent rerun is
  `UBC-FRESH/femic-tsa23-instance` #11. Dashboard: **GREEN**.
- P16 close-out: parent issue #141 closed. P16.2 was merged as `8f0f6d4` (pull request #142), P16.1 is
  the negative matched-footprint result above, and P16.3 is the account's scope recorded in
  `docs/reference/spatial.rst` and `notes/design/ws4-spatial-accounts.md`. The report is
  `notes/reports/p16-closeout.md`. No new phase is proposed: the result is a paper-scope decision, and
  the next WS4 item (P13's route-report `LENGTH`) waits on the maintainer.
- P17.1–P17.4 **roads dated to the period.** `RouteNetwork` carries an opened set: a network built with
  `initial_open` set to the zero-build-cost segments starts from the roads that exist, routes only over
  opened segments, and opens a planned path when a block first needs it. Existing roads are treated as
  already built, so they are not counted as `BUILTLENGTH`; planned roads are charged in the period they
  open. A route prefers an opened road to a shorter unopened one, and the Dijkstra and assignment caches
  are invalidated when the set grows. Declarable as `route.initial_roads: existing|all` in a route
  config (default `all`, the pre-P17 behaviour). Tests: `tests/test_roads_opened.py` (six cases).
  **The first 2026 measurement is a partial success and is recorded rather than claimed:** period 1
  (`tmp/parity2025/run-dated`, MILL1) moves `BUILTLENGTH` from 730,679 to 386,352 and `BUILD_EXPENSE`
  from 2.02M to 1.93M against the reference's 732,073 / 3.66M, but `LENGTH` moves only 4.5% (3.07M to
  2.93M) and remains **2.55×** the reference's 1,149,647. The cause is the road *choice*: the existing
  set is dense (4.42M m) and the router prices haul only, while the reference's solve uses a compact
  network and trades haul for road (its haul expense is 1.8× WS4's). P17.5 names the two levers — a
  road-aware route cost, or fitting the initial set — and the phase stays active. Report:
  `notes/reports/p17-opened-roads.md`. Dashboard: **GREEN**.
- P17.2 correction **the route report was summing `LENGTH` across the period's years.** The period
  report treated `LENGTH` as an extensive column, so with `period_width = 10` a road used in nine years
  counted nine times: MILL1 period 1 read 2,931,907 m. The reference reports the **distinct road used at
  any time in the period**, counted once. The report now unions the segment ids over the period and sums
  their lengths once; the expenses and volume remain sums, and `BUILTLENGTH` was already a one-time
  quantity. Corrected period 1: **882,027 m against the reference's 1,149,647 (0.77×)**, not 2.55×.
  `BUILTLENGTH` 386,352 (0.53×), `BUILD_EXPENSE` 1.93M (0.53×), `HAUL_EXPENSE` 6.29M (0.56×), `VOLUME`
  1.02M (1.00×). The 2.55× figure, and the joint-assignment hypothesis built on it, were artifacts of
  the aggregation and are withdrawn. The remaining discrepancy is `MAINTAIN_EXPENSE` at **3.22×** while
  road use is lower — P17.5 is re-scoped to the maintenance charging period and rate. Tests updated
  (`tests/test_roads.py` asserts a route used in ten years is 300 m, not 3,000). Report:
  `notes/reports/p17-opened-roads.md`. Dashboard: **GREEN**.
- P17.5 **maintenance is charged once per period, not once per year.** The ledger charged each used
  segment in every year and the report summed the period's years; the reference charges a used segment
  once a period. Charging once over the period's union gives **1,052,489** against the reference's
  **1,126,465 (0.93×)**, where the per-year sum was 3,622,033 (3.22×). The charge is booked in the first
  year of the period in which the segment is used, so an annual route account still carries a value and
  a period sums it once. With this, the **accounting definitions match** the reference: distinct road
  per period, maintenance once per period, volume summed, builds charged once. What remains is
  **behaviour**: WS4 builds and uses less road (`LENGTH` 0.77×, `BUILTLENGTH` 0.53×, `BUILD_EXPENSE`
  0.53×) and hauls for less (0.56×) while moving the same volume (1.00×) — the reference's road/haul
  trade-off, now a modelling difference rather than a reporting artifact. Report:
  `notes/reports/p17-opened-roads.md`; the remaining question is P17.6. Dashboard: **GREEN**.
- P17.6 **the road/haul trade-off is a model difference, not an accounting one, and the last P13 item
  is closed.** With the period accounting matched, the 2026 period-1 decomposition says: build cost
  **per metre is identical** (5.00 both) — the reference builds 1.9× the length; WS4 hauls **22%
  farther** (61.4 against 50.3 km) but on roads costing **0.46× per unit-km**, for a net haul of 0.56×;
  road use and maintenance are close (0.77× and 0.93×). WS4 minimises haul over the roads that exist;
  the reference solves the road set and the block-to-mill assignment jointly under its targets. The
  divergence is named in the parity mode (*road selection and haul routing*) rather than tuned with an
  uncalibrated road price: a weight fitted to one period would be an artifact, not the reference's
  objective. `AVERAGEHAULDIST` is now reported in **kilometres** (the reference's unit; the model still
  routes in metres), which closes P13's last item — the route report's distance unit. Reports:
  `notes/reports/p17-tradeoff.md` and `p17-opened-roads.md`. P13 and P17 are complete. Dashboard:
  **GREEN**.
- P18.1 **the optional web service, and the front-end design.** `ws4[web]` (FastAPI + uvicorn) serves
  the artefacts a run already wrote: the dataset manifest and runs (`/api/summary`), a run's summary,
  its account values, its reports, and a treatment layer joined to a GeoJSON geometry file; the targets
  YAML is readable and replaceable, with the optimizer's own loader as the validator (an invalid edit is
  a 422 and the file is left unchanged). The bind is loopback-only unless `--allow-remote` is passed.
  The design — the artefact contract, the SSE contract, the skin manifests, and the MapLibre interface
  — is `notes/design/ws4-web-frontend.md`; the API is `docs/reference/web.rst`. The core install is
  unchanged; the service is an extra, imported lazily by `ws4 serve`. Tests: `tests/test_web.py`
  (seven cases). Dashboard: **GREEN**.
- P18.2 **the browser shell, first cut.** The service now serves a dependency-free application
  (`ws4/web/static/`) over its own artefacts: a run selector, a year control taken from the schedule,
  treated/untreated layers with counts, click selection, wheel-zoom/pan, and the Legend/Targets/Reports
  tabs. `GET /api/runs/{run}/periods` supplies the run's period range, and `/map` returns **every**
  block with `treated` and `treatments` properties so the client styles and toggles without a second
  request. `Simulator.run` now records the schedule it replayed in the run directory (guarded when the
  run is written into the schedule's own directory), which is what the map joins against. The static
  files ship in the wheel (`package-data`). It works at `/` and under a proxy prefix because every URL
  is relative. A run directory with `account_values.csv` but no `summary.json` is listed as a
  `simulate` run; a directory with neither is not offered. Tests: nine service cases. Dashboard:
  **GREEN**.
- P18.3 **the targets panel, first cut.** The service exposes the parsed targets as JSON
  (`GET/PUT /api/targets.json`) so the browser needs no YAML parser; a PUT is serialized to YAML and
  validated with the optimizer's own `load_targets`, so an invalid edit is refused exactly as the CLI
  would refuse it. The Targets tab renders a table per account and period with editable minimum,
  maximum and weights, saves through that path, and shows the realized value from the selected run's
  own `account_values.csv` with a met/below/above status. Remaining: the active toggle and the resolve
  action. Tests: ten service cases. Dashboard: **GREEN**.
- P18.4–P18.5 **reports and skins, first cut.** The Reports tab lists the run's own report files and
  renders a CSV in a table (first 200 rows) while HTML/PNG reports open directly — nothing is
  recomputed in the browser. Four skin manifests (`model-builder`, `scenario-analyst`,
  `scenario-browser`, `reviewer`) are checked against a panel/layer/action registry when the service
  starts; an unknown name is refused by name, a duplicate id is refused, and a read-only skin may not
  carry a mutating action. `/api/skins` exposes them, and the shell applies a skin by hiding panels and
  disabling the target editor; the rule lives on the server. Tests: `tests/test_web_skins.py` (four
  cases) and the service cases (fifteen total). Dashboard: **GREEN**.
- P18.3 **the live run.** `POST /api/runs` starts a search with the configured dataset and targets —
  **refused unless the service was started with `--allow-runs`** — and the command is composed by the
  service, so the request body can choose only iterations, seed and horizon (both bounded). The run is
  spawned as the CLI subprocess, keeping the design rule that a search cannot take the service down;
  its console goes to the run directory. `GET /api/runs/{run}/events` replays `telemetry.jsonl` as SSE
  `progress` events and closes with `done` (the run's own summary) or `error`. The Targets panel gains
  Iterations/Seed and **Run search**; on completion the run list, periods, targets, reports and map
  refresh onto the new run. Verified end to end: a 5-iteration run produced its summary and the stream
  delivered each step. Tests: the read-only refusal, the no-targets refusal, and the SSE replay
  (eighteen service cases). Dashboard: **GREEN**.
- P18.3 **realized target values use the target's period, not a single year.** The web UI had compared
  a target against the account's value at the target's end year, so a ten-year product flow was read as
  one year (15,130 against a 1.2M floor instead of 1.89M). `GET /api/runs/{run}/targets` now computes
  each target's realized value with the optimizer's own `period_value` — a product sums its period, a
  feature reads the period's end — and the live `targets` SSE event is transformed the same way, so the
  table, the window cards and the live updates all read the quantity the optimizer prices. Tests cover
  the product sum and the feature level. The demo targets are now the reference's own period-1 levels
  for `product.Yield.managed.Conif` (1.2M) and `feature.Yield.managed.Conif` (8,318,543.5); both are
  above their exact levels, which is the honest status for a run that does not meet them.
- P18.3 **the search is a player: play, pause, stop, and continuous by default.** The optimizer now
  polls a control file (`ws4/opt/control.py`) every sixty-fourth iteration: `pause` holds the loop and
  `stop` breaks it, so the best schedule is returned and the run writes its usual schedule and summary
  instead of being killed. `--control-file` exposes it; the service writes `control.json`, starts a
  **continuous** run (a very large budget, 24-hour safety) unless iterations are given, and exposes
  `POST /api/runs/{run}/control` plus a `paused` flag in status. The UI's Run search is now
  **Play/Pause + Stop**, with max iterations 0 meaning until stopped and an optional `HH:MM:SS` limit.
  The SSE stream is **coalesced** to one progress record, one targets snapshot and the merged schedule
  diff per poll — a fast solver had been emitting hundreds of events per second and constantly
  re-laying out the panel, which also made the pause button unclickable. Tests: the control file and
  poll interval, the pause/resume/stop endpoint and status. Verified in the browser: Play → Pause
  (Resume) → Stop, with the run ending in `done` and its summary written.

## 2026-10-20

- P18.3–P18.5: the targets table, the report preview, the four checked skins and the live player are
  on `feature/p18-reports-skins`. The player starts a continuous search by default, pauses/resumes and
  stops through the run's `control.json`, and keeps the selected year when the run finishes.
- Target watchers span the run's whole horizon: a point per period, the target band only where a
  target exists, and the realized value folded by the target's own period rule (a product sums its
  period; a feature is a level at the period's end). The live targets event carries the tracked
  accounts' yearly series, so the card updates while the search runs. The default year follows the
  first target.
- P18.5 live runs use parallel islands (`islands` on the start request). Each worker writes its own
  `telemetry-<island>.jsonl`; the canonical `telemetry.jsonl` is merged after the search. This
  removed a single-writer bottleneck that made an eight-island run display hundreds of iterations a
  second while the solver was doing thousands. The event stream follows the best island, resets the
  map when that island changes, and reports the aggregate step count. The shared absolute deadline
  now reaches the workers, so a time-limited parallel run stops all of them.
- Added the embedded assistant in the lower-left panel: `POST /api/chat` runs one turn through the
  installed OpenCode CLI with the configured model (`--agent-model`), keeps the CLI's own login, and
  returns the reply, tool actions and session id. `--allow-agent` is a separate, off-by-default
  permission because the agent has the service user's shell and filesystem; the docs name the risk.
- Dashboard result: `python scripts/dashboard.py` reports `OVERALL: GREEN` on all seven gates.
- P18.5 follow-up from the Codex review and a live-service incident: a finished run's
  `/api/runs/{run}/events` now returns 204 so an EventSource stops reconnecting (a buffering proxy
  had turned a completed run into 342 open connections and exhausted the service's thread pool);
  live streams close after ten minutes and reconnect. The skin selector is cleared before its options
  are rebuilt and keeps the analyst's choice across run changes, and a non-CSV report name is built
  with `textContent`, closing the filesystem-name markup finding. Dashboard result:
  `python scripts/dashboard.py` reports `OVERALL: GREEN` on all seven gates.
- P18.6: added the **Compare** tab. Two completed runs are read through the existing `map?year`,
  `accounts?year` and `targets` endpoints; the map colors blocks treated only in A, only in B and in
  both at the selected year, the target table shows both period values and statuses, and the account
  table lists the B − A delta sorted by absolute change with a filter. All four skins expose the
  panel. Browser check: `run-dated3` vs `web-20261020-160641-1` at year 9 gave 15 A-only, 47 B-only
  and 1 both blocks, 2 target rows and 60 account rows with no console errors. Dashboard result:
  `python scripts/dashboard.py` reports `OVERALL: GREEN` on all seven gates.
- P18.2 first slice: the Legend tab is now a grouped layer tree. It reads
  `/api/runs/{run}/layers` and offers current treatment, cumulative through year (current red,
  earlier tan), and patch size classes from `patch_membership.csv`, with a checkbox per class. A run
  with no schedule gets its period range from patch membership or account values, so
  `run-harvested-flow` is readable. Roads and spread compartments are shown as unavailable with the
  reason: run outputs carry no segment geometry or compartment membership. Browser check: year 9 of
  `run-dated3` gives 16 current and 1,155 earlier blocks; `run-harvested-flow` shows 16 patch blocks
  in four classes, and unchecking 0–10 leaves five. Dashboard result: `python scripts/dashboard.py`
  reports `OVERALL: GREEN` on all seven gates.
- P18.2 block geometry: the map now draws the source `blocks.shp` stand polygons, simplified to a
  5 m tolerance (12,567 polygons, 13.6 MB GeoJSON) instead of centroids. The service parses the
  geometry once and each layer request reuses it; paths keep a boundary stroke, current treatments
  are solid red, earlier cumulative treatments use a diagonal hatch, and patch classes keep their
  distinct fills. Live schedule updates touch only the blocks in the diff rather than rebuilding all
  paths. The source `COMPART` value is shown in the block detail. Web-run startup also accepts
  `--topology`/`--patch-accounts`/`--spread-accounts`/`--block-coordinates`/`--route-config`, so a
  configured run can write patch membership. Browser check: 12,567 paths, no circles, 1.3 s first
  render, live updates from 0 to 224 treated blocks with no console errors. Dashboard result:
  `python scripts/dashboard.py` reports `OVERALL: GREEN` on all seven gates.
- P18.2 base colours: the stand polygons now support a source-attribute base mode — compartment,
  THEME2, THEME5, MartStrata or LMU — selected from the layer tree, with a scrollable category
  legend and a deterministic hue per value. The base view is static and source-derived; no model
  value is recomputed, and the treatment/cumulative/patch modes keep their fills and hatch. The
  block detail lists the source attributes. Browser check: 30 compartments and 10 THEME5 classes
  render as coloured polygon mosaics; switching back to "Off" restores the current-treatment map.
  Dashboard result: `python scripts/dashboard.py` reports `OVERALL: GREEN` on all seven gates.
- P18.3/P18.4: targets have an **active** flag. The web table's On checkbox writes it to the same
  YAML; `Target.active` defaults true, the objective and the incremental evaluator skip inactive
  targets, and the target report calls them `inactive` without a penalty. The Reports tab now groups
  the named standard reports the run wrote and adds a Build a report form over accounts and years
  with a CSV export. Browser check: toggling the product target off saved `active: false`, the run
  reported it `inactive`, and its watched card read `off`; the builder produced 10 rows for
  `feature.Yield.managed.Conif` over years 0–9 and enabled the CSV download. Dashboard result:
  `python scripts/dashboard.py` reports `OVERALL: GREEN` on all seven gates.
- P18.2 source road overlay: `serve --roads` accepts a GeoJSON line layer of the source access
  network; `/api/roads` serves it and the Legend tree adds a lazy **Access roads (source)** overlay.
  The overlay is 36,721 lines (7.3 MB GeoJSON), off by default, and renders as thin source lines; the
  run's used-road subset and model spread-compartment membership remain named follow-ups. Browser
  check: ticking the overlay drew 36,721 lines with no console errors; unticking cleared them.
  Dashboard result: `python scripts/dashboard.py` reports `OVERALL: GREEN` on all seven gates.
- P18 phase complete. The optional web service, live player, map/layer tree with simplified source
  polygons, source base colours and source access roads, active targets, standard/builder reports,
  four skins, comparison and the embedded local assistant are merged. The close-out report is
  `notes/reports/p18-closeout.md`; the run's used-road subset, model spread-compartment membership,
  MapLibre and a stability stopping criterion are recorded in `notes/backlog.md`. No settings, tag or
  release changes. Dashboard result: `python scripts/dashboard.py` reports `OVERALL: GREEN` on all seven
  gates.
- P19 started on `feature/p19-spatial-layers` (parent issue #161): model spread-compartment
  membership, the run's used-road geometry/use, a stability stopping criterion and map scale. The
  P18 close-out and backlog record the source-layers boundary.
- P19.1: the simulator writes `spread_membership.csv` (the untreated blocks of every spread
  compartment, largest first); the service serves it as `layer=compartments` and the web layer tree
  colours the components by area class with the account selector and the period's treated breaks.
- P19.2: route runs write `used_roads.csv` with the used segments' vertex geometry (when the
  vertices table has coordinates); the service serves the year's used roads as a GeoJSON overlay
  and the web layer tree draws it distinctly from the source access layer.
- P19.3: a stability stop (`patience`) ends a start after a configurable run of iterations without
  an incumbent improvement; the optimizer/CLI record it in the summary, and the web player exposes
  the field beside its iteration and time limits.
- P19.5: the map control steps by accounting periods (the targets' `period_width`) rather than
  years, labels the period with its year range, sends the period range to the map, and pages with
  left/right arrow keys.
- P19.6: the lower-left assistant has a draggable height splitter (persisted, double-click resets)
  so a long conversation can use more of the sidebar.

## 2026-10-21

- Spatial penalties are now part of the move-delta objective. `SpatialPenaltyModel` keeps the
  selected blocks per year and each block's disturbance years, recomputes opening/core-area
  penalties only for the affected years and green-up only on incident edges, and the incremental
  evaluator adds that delta to the account-target delta. The optimizer therefore keeps the faster
  delta path when `max_opening_ha`, `min_green_up_years` or the core-area rule is active; the
  whole-schedule path remains the fallback for build-route, edge-contrast and spread accounts.
- `ws4 optimize` accepts `--initial-schedule` (a `block_id,treatment,period` CSV) and
  `--spatial-weight`; the initial schedule is serial-start only. The optimizer summary records the
  initial schedule path.
- Added exactness tests: a random spatial walk, the spatial delta SA, and the
  core-area rule match a fresh whole-schedule evaluation on the synthetic fixture.
- Targets are indexed by accounting period in the target file: `period: 1` is the first
  accounting period (years 1 to `period_width`), and `period: 0` is the initial snapshot. `year` and
  the year-based flow keys remain accepted for older files; a period key takes precedence. Flow
  windows gained inclusive `flow_start_period`/`flow_end_period` and `flow_reference_period`.
  Reports and the web target table now carry the period beside the derived year. Full suite: 658
  passed; dashboard GREEN.
- Added a `coalesce` move: it grows a connected cluster, takes a target treatment year from the seed
  block, and rechooses the other members onto candidate chains that treat them in that year. This
  is the patch-shaping counterpart to `cluster` (which rechooses members independently) and `merge`
  (which only fills partial-membership gaps). Exposed as `--coalesce-weight`, `--coalesce-size`, `--coalesce-min-area-ha`
  and `--coalesce-max-area-ha`; the cluster grows until its criterion-weighted area is
  inside the band (default 5-40 ha). Covered by a connected-cluster test. Full suite:
  659 passed; dashboard GREEN.
- The web target table now keys rows by target index and reports flow targets from their
  percent series rather than the account's period value. Harvest and even-flow targets on the
  same account/year no longer collide, and the flow status is `met` only when every compared
  period is inside its band. The watch panel excludes flow targets, whose series is a percent
  profile rather than an account level. `patch_first_search` now shows all 52 target rows met.
  Full suite: 659 passed; dashboard GREEN.
- #165: `--seed-greedy --seed-account ACCOUNT` builds a schedule that reduces a named
  maximum target (the hazard-shaped case) under its other maximum targets' cost ceilings.
  The default `--seed-greedy` floor mode is unchanged.
- #165 speed: a feature reduction goal shortlists blocks by the direct feature curve
  before exact candidate scoring, and the reduction-goal seed scores the shortlist in
  forked workers. The exact seed still builds and verifies the schedule.
- P19.4: MapLibre GL JS with an OpenStreetMap raster basemap is the default map renderer, with
  the SVG shell kept as a switchable fallback. The service transforms the source CRS to WGS84 for
  MapLibre (`--crs`, `format=wgs84`); the layer, period and selection contracts are unchanged.

- The schedule clock is now a single 0-based `offset` clock everywhere. A schedule CSV carries
  `offset` (offset 0 is the first simulation year); the legacy `period` schedule column is rejected.
  Account values, optimizer chains, patch/spatial state, road ledgers and the web API all speak
  offsets. Accounting period 0 remains the zero-length pre-simulation snapshot at offset -1, and
  period `p >= 1` covers offsets `(p-1)*period_width` through `p*period_width - 1`. `year` is a
  display label only (`year = offset + 1`). This removes the old conflation of the schedule's
  0-based step with the accounting period and the resulting off-by-one and period-0 treatment bug.
  The TSA 48 builders emit `offset`, and the calibrated TSA 48 model is rebuilt on the corrected
  clock. Full suite: 665 passed; dashboard GREEN.

## 2026-10-23

- Added the optional `--land-base` polygon to `ws4 serve` and a pale underlay layer under the
  blocks. The TSA 48 full and NICC instances now pass their gross AOI so non-forest gaps read as
  land rather than missing geometry; the map still works without the flag. UI build v43.
- Added the clean-checkout contract test and CI job: the tracked synthetic recipe builds a matrix,
  a patch-first schedule on the offset clock is simulated, and the period target table is read
  through the web API. The test is part of the normal suite and has its own named CI job.
- Cut the MKRF and North Island docs over to ws4 as the primary runtime, with the retained
  Patchworks packages marked reference/interchange-only. Full suite: 667 passed; dashboard GREEN.
- `ws4 simulate` now accepts `--patch-accounts` and `--patch-membership`, so a run can write the opening-size distribution it used without going through the Python API. The schedule help now names the offset clock. Full suite and dashboard remain green.
- The web period control now reads the simulated horizon from account values as well as the schedule, so a 300-year run keeps a 300-year slider even when the schedule stops earlier. Changing periods preserves the current map view instead of refitting. UI build v45.
- The chat panel retries once after a 502/503/504, which recovers the common cold first turn through the reverse proxy. The map legend now distinguishes all treated blocks from connected patch openings. UI build v46.
- When a service has a run named `reference`, the UI opens that run by default. This makes the NICC reference target set the first thing an analyst sees; services without a reference run keep the old first-run behavior. UI build v47.
- Added viewport level-of-detail to the map endpoint and the MapLibre shell. `bbox` limits the
  response to intersecting features, and `zoom` below 10 returns compact block centroids. Treatment
  layers return treated centroids only at the overview scale, and the bare block layer returns an
  even sample; the response carries full-run treated/untreated totals. The shell reloads after a
  debounced `moveend` and keeps the current view. The TSA 46 initial payload fell from 444 MB to
  66 KB at zoom 5; a zoom-12 viewport is 524 KB. Tests: 46 web tests, mypy, ruff, validator, docs.
- Added the MVT tile endpoint and the MapLibre vector source for the block, treatment, and
  cumulative layers. `GET /api/runs/{run}/tiles/{z}/{x}/{y}.mvt` returns treated centroids below
  zoom 10 and simplified polygons above it, with an in-memory tile cache; `map-stats` keeps the
  full-run counts. The TSA 46 zoom-0 tile is 8.5 KB (331 treated blocks); a zoom-12 tile is 3.1 KB
  and 57 ms once the source payload is cached. Patches, compartments, and comparison keep the
  GeoJSON path.
- P20.2 correction: the MVT tile endpoint, `map-stats`, and the in-memory tile cache are in
  place, but the MapLibre vector-source integration did not request tiles in a headless-browser
  check, so it is deferred to P20.3. The shell keeps the verified viewport GeoJSON path; the
  endpoint remains available and tested for a vector-source client.
- P20.1 fix: the shell now creates the MapLibre map before waiting for readiness, retries the first
  load instead of deadlocking, and reloads the viewport only after a user drag or zoom. The TSA 46
  initial request is 66 KB at zoom 5 with 331 treated centroids; the full-run counts come from the
  response's totals. This is the verified shell path while P20.3 owns the vector-source integration.
- P20.3 wires the MVT endpoint into the MapLibre shell. The vector source installs after the map
  is idle, uses `setTiles` for period/layer changes, and keeps the viewport GeoJSON path for
  patches, compartments, and comparison. The TSA 46 shell makes six z6 MVT requests on load
  (331 treated centroids of 171,825 blocks); TSA 47 makes four z7 requests (456 of 74,170).
  `scripts/check_map_browser.py` is the opt-in Playwright smoke; both services pass it.
- P20.4 adds a durable MVT tile cache (`ws4 serve --tile-cache`) with `X-WS4-Tile-Cache` reporting
  `memory`, `disk`, or `miss`, and the 1,000,000-fragment scale gate. The gate measured a 130 KB
  zoom-0 tile in 29.3 s cold and 0.018 s warm, and a 2.8 KB zoom-12 tile in 0.038 s; all
  thresholds pass. Tests: disk/memory/miss cache, grid writer, and scale smoke.
- P20 is queued for approval. The close-out report is `notes/reports/p20-closeout.md`, the pull
  request is #185, and the roadmap/tracker say `pr-open`. The evidence includes the 66 KB TSA 46
  viewport, the 8.5 KB z0 and 3.1 KB z12 tiles, the disk/memory/miss cache check, the browser
  smoke on both TSAs, and the 1,000,000-fragment scale gate (29.3 s cold, 0.018 s warm).

## 2026-10-24

- P21.1: `ws4 optimize --reversion N` resets the current solution to the incumbent every N
  accepted moves in SA, tabu, and ILS. The run summary records `reversion`; the optimizer reference
  explains the intensification step. Tests cover the helper, the config check, and a run.
- P21.2: `scripts/validate_search.py` runs SA, tabu, and ILS over several seeds with the same
  targets and budget, then reports best/mean/median/worst, population standard deviation,
  zero-penalty status, and the MIP gap when `--mip-bound` is set. It writes JSON and Markdown.
  The dashboard is green.
- The validation sweep accepts `--reversion`, so a run can compare a reverted search with the plain one. Tests: 6 validate-search tests; dashboard **GREEN**.

- P21.4: added the threshold-accepting engine (`--engine threshold`, `--threshold`, `--cooling`).
  It accepts improving moves always and worsening moves within the current threshold, shrinks the
  threshold each iteration, and shares `--patience` and `--reversion`. `ws4 optimize` now exposes
  `--engine` for sa, tabu, ils, and threshold; `ws4 watch` accepts the same alias. Tests cover the
  parameter guard, an optimizer run, and unknown-engine rejection. Dashboard **GREEN**; one
  `test_web.py` tile test failed once under load and passed in three isolated and two full reruns.

- P21.3: added `scripts/sensitivity.py`, an advisory report over a run's `report_targets.csv` and
  the target file. It reports each target's shortfall, excess, nearest-bound slack, binding status,
  and the per-unit objective weight that applies outside a bound. It writes JSON and Markdown. This
  is the goal-programming slack view, not an LP dual; true LP dual sensitivity remains a follow-up.
  Tests: 4 sensitivity tests; dashboard **GREEN**.

- P21 close-out: reversion, the validation sweep, the sensitivity report, and the threshold-accepting
  engine are implemented, tested, documented, and queued for review in `notes/reports/p21-closeout.md`.
  Dashboard **GREEN** at `37c16e6`.
- P20.6 corrects the map's geometry policy after the first LOD was rejected as a point/grid
  scatter. The service uses `fragments_full.geojson` for detail zooms and a 100 m overview below
  zoom 8; below zoom 6 treatment layers show treated block polygons, and zoom 6+ shows every
  block. The centroid and grid MVT paths are removed. Measured: a z12 tile is 4.98 KB / 74 full
  block polygons; a z6 overview tile is a 65,268-block mosaic; the map is exact at the zooms where
  it matters.
- P20 is complete. Pull request #185 merged as `2123252`; the P20.6 exact-geometry correction is
  `ed9693e`. The close-out report now records the rejected centroid/grid LOD and the final policy:
  full geometry at detail zooms, a 100 m overview below zoom 8, and treated-only block polygons
  below zoom 6.
- P20.6 cache-bust: tile URLs now carry `v=v8`, the server cache is v8, and block outlines are
  visible. A sampled z13 tile is 57 full block polygons, 0 invalid; the browser no longer reuses
  the pre-fix 100 m tiles.

- P22.1: `scripts/prewarm_tiles.py` walks a model tree's bounds and selected zooms/layers/periods
  in-process, writes the durable MVT cache, and reports requests, failures, bytes, seconds, and
  cache-header counts.
- P22.2: `scripts/check_map_proxy.py` mounts the service at a path prefix and verifies the shell,
  static assets, API summary, viewport map, and MVT tile; it also asserts the relative URLs that
  make a prefix work.
- P22.3: `scripts/benchmark_map_scale.py` now reports peak RSS and enforces a 4096 MiB budget. The
  1M-fragment gate measured 130 KB z0 / 25.19 s cold / 0.018 s warm / 1,734.6 MiB peak. The gate
  caught a real regression: the bare block MVT layer was not sampled below zoom 6, producing a
  27 MB z0 tile; it now samples to 5,000 features and returns to 130 KB. Dashboard **GREEN**.

- P22 close-out: pre-warm, path-prefix deployment check, and the 1M peak-RSS gate are implemented,
  tested, documented, and queued in `notes/reports/p22-closeout.md`. The scale gate caught and fixed
  the missing low-zoom block sampling. Dashboard **GREEN** at `57a98dd`.

- Refresh the stored outputs of `010_quickstart`, `030_sample_estate`, `040_patch_targets`, and
  `050_routes_and_mills` after P21 added `reversion 0` to the solver banner. The `Notebook outputs`
  gate is green again; no solver behavior changed.

- P24.1: `ws4.opt.archive` keeps elite schedules with their objective, realized metrics,
  seed, and source; filters a stable nondominated front under explicit max/min directions;
  and exports `archive.json` plus one schedule CSV per elite.
- P24.2: `scripts/portfolio.py` and `ws4.opt.portfolio` vary target-weight factors over a
  grid and seeds, record every member, and write `portfolio.json`, `portfolio.md`,
  `front.csv`, and the elite archive.
- P24.3: `scripts/tune.py` and `ws4.opt.tune` run grid or seeded-random candidates over
  `OptimizeConfig` fields, rank by best and median objective, and write `tuning.json`,
  `tuning.md`, and `best.json`.
- P24.4: the option-selection program is shared by the MIP and the new LP relaxation;
  `scripts/lp_sensitivity.py` reports target duals and option reduced costs with HiGHS.
  The real synthetic-estate smoke produced a binding floor dual of 1.0 and reduced costs
  360/340 on the two CC options. Dashboard **GREEN**.

- P25.1: `--constraint-strategy penalize|reject|repair` wraps the operator registry with a
  constraint guard. Reject refuses an infeasible proposal; repair tries a one-block local
  repair; penalize remains the default incremental path. The guard counts proposed,
  feasible, rejected, and repaired moves and repairs an infeasible seed.
- P25.2: the run summary records `constraint_strategy`, `constraint_stats`, and
  `constraint_feasible`; each run writes `constraint_report.json` with the final spatial
  violations. The synthetic constrained run reported 22 proposed, 13 feasible, 9 rejected,
  and zero final violations under reject and repair.
- P25.3: `scripts/max_flow.py` binary-searches a constant per-period volume floor with the
  existing optimizer, preserving the non-volume targets and writing `max_flow.json`,
  `max_flow.md`, `probe-config.json`, the probe log, and `best-schedule.csv`. The high bound
  is an additive envelope and the ceiling is advisory. Dashboard **GREEN**.
- P25.2 refresh: the example notebooks' stored outputs now include the new
  `constraint_strategy` summary field. `python scripts/check_notebooks.py` reports 47
  compared and 0 drifted.
- P23.1: the Targets tab now reads the selected run's account catalogue, folds the names on their
  `.` segments into a searchable tree, and shows each account's last value, its level/flow rule, and
  a `target` badge when it is already targeted. Selecting a leaf opens a period/width/min/max/weight
  form; **Add target** validates the whole list through `POST /api/targets.json`, writes the YAML,
  and refreshes the table. The table's **×** removes a target; the last target cannot be removed
  because the API refuses an empty document. The width defaults to the file's existing width, or ten
  years when the file is empty. Target `notes` fields survive the JSON round-trip; comments and key
  order do not, which the web reference now states. The shell assets move to `v50`, and the tile base
  now resolves without the page query so `?v=50` works. Verification:
  `scripts/check_target_browser.py` opened 51 accounts, filtered to an account, added and removed a
  target against a scratch targets file; the empty-file path was tested separately; the P20 tile
  plots at z13-z15 remain normal block mosaics. Dashboard **GREEN**.

- P23 close-out: the account browser and target activation are implemented, tested, documented, and
  queued in `notes/reports/p23-closeout.md` (PR #212, evidence head `934e288`). The report records
  the empty-file path, the notes-preserving round-trip, the last-target guard, and the period-label
  follow-up. Dashboard **GREEN**. The P22 close-out now records its merged status and moves the
  search-portfolio recommendation to P24 (planned).

- P23.1 follow-up: Play and Stop were wired inside the SVG-only `fit()` helper, so a MapLibre
  page had no click listener and pressing Play did nothing. The listeners now live in
  `wireControls` and are installed once. Verified on the c5 sample: the button moved to Pause,
  `POST /api/runs` returned 200, progress appeared, and a run started from a target added in the
  Targets tab wrote that account to `report_targets.csv`. Added the opt-in
  `scripts/check_run_controls.py`. The service now refuses `--patch-accounts` without `--topology`
  (and spread accounts without both inputs) instead of starting a doomed run, and the optimizer
  names the missing topology; tests cover both. Shell assets move to `v51`. Dashboard **GREEN**.

- P26.1: every optimizer run writes `run_manifest.json` with the code revision, dataset reference
  and hashes, full configuration, seeds, environment, and a reproduce command.
- P26.2: every run writes `data_quality.json` and a compact `data_quality` summary block covering
  manifest metadata, table counts, target-account coverage, and explicit unknowns/limitations.
- P26.3: `scripts/compare_scenarios.py` compares labelled runs, writes JSON/Markdown/CSV tables, and
  reports an optional Pareto front over named metrics. Dashboard **GREEN**.
- P26.1-P26.2 refresh: the example notebooks' stored outputs include the new run-manifest and
  data-quality summary fields. `python scripts/check_notebooks.py` reports 47 compared and 0 drifted.

- P27.1: `normalization: auto` divides a target's weighted penalty by its larger absolute
  bound (floored at one), and `report_targets.csv` carries raw/normalized penalties and scale.
  The MIP/LP option model uses the same scale.
- P27.2: `priority` tiers use a `1e9` step multiplier in the scalar objective. Default priority
  one leaves the current objective unchanged; the incremental evaluator and full objective agree.
- P27.3: sensitivity reports the effective normalized marginal, the web target rows carry
  normalization/priority, and scenario target tables preserve the new columns. Dashboard **GREEN**.
- P27.3 refresh: the example notebooks' stored target tables include `raw_penalty`, `scale`,
  `normalization`, and `priority`. `python scripts/check_notebooks.py` reports 47 compared, 0 drifted.

- P28.1: `report_targets.csv` carries a `kind` field (level, flow.even, flow.ndy), and every run
  writes `ending_inventory.csv` plus a summary block for the final feature-account values.
- P28.2: the flow-ceiling probe accepts `--flow ndy|even` and `--flow-tolerance`, adds the flow
  target to each probe, and reports floor and flow feasibility separately with the worst change.
- P28.3: scenario comparison writes `scenario_ending.csv` and `scenario_flows.csv` and names both
  in the Markdown report. Dashboard **GREEN**.
- P28.1-P28.3 refresh: the example notebooks' stored target and ending-inventory tables include
  the new `kind` and inventory surfaces. `python scripts/check_notebooks.py` reports 47 compared,
  0 drifted.
- P23.1 follow-up: the run control is now **Solve**, without the media triangle, and **Max iters**
  defaults blank as ∞. A blank or zero value starts a continuous run with no default wall-clock cap;
  the old 24-hour limit is removed, and Pause/Stop are text controls. `scripts/check_run_controls.py`
  now asserts that the default POST returns `continuous: true` and an empty `time_limit`, then stops
  the run. Shell assets move to `v52`. Dashboard **GREEN**.

- P23.3: added `GET /api/geometry/bounds?format=projected|wgs84`, which returns the configured
  geometry's extent and transforms the four corners for a projected CRS. The MapLibre vector path
  now fits the view to that extent once per page before loading tiles, so a service without a
  land-base layer no longer opens at the hard-coded BC-wide centre. On the c5 service the shell
  moved from z5/BC to z9 over the AOI and rendered the block mosaic. Tests cover the endpoint,
  the no-geometry 404, and the bad-format refusal; the web reference documents it. Shell assets
  move to `v53`. Dashboard **GREEN**.

- P23.4: the metaheuristic solvers now emit a trace with the current solution's objective and the
  accepted-move count, alongside the incumbent. Telemetry step records carry `current` and
  `accepted`; the SSE progress event keeps the incumbent `objective` but merges the latest trace,
  so a flat best is visibly different from a stalled search. The run panel shows
  `best · current · accepted`. On c5, best stayed at 3,965,293 while current moved to 3,965,632 and
  accepted rose past 30. Solver, telemetry, and SSE tests cover the fields; shell assets move to
  `v54`. Dashboard **GREEN**.

- P29.1: `ws4 solve-mip` solves the option-selection model for a small instance or block subset,
  replays the schedule, and writes `mip.json`, `schedule.csv`, `account_values.csv`, and
  `report_targets.csv` with the model boundary named.
- P29.2: `scripts/exact_vs_heuristic.py` runs the exact lane and a heuristic under the same
  targets/budget and writes both schedules plus a JSON/Markdown gap report.
- P29.3: `ws4 optimize --lp-bound` records `lp_bound`, `lp_gap`, and `lp_status`; validation and
  scenario comparison carry the MIP/LP bound and gap fields. Dashboard **GREEN**.
- P30.1: whole-schedule solvers (`solve_sa`, `solve_threshold`, `solve_tabu`, `solve_ils`) now emit
  `targets` and `schedule` snapshots every twentieth iteration; the engine builds a realized-cell
  snapshot from the incumbent. Patch/route c5 runs therefore animate the map and update target cards
  during the search, not only at completion. Fixed the browser's live-target key: it looked up
  `state.targetCells` by `year|account` instead of the target index, so the cards never repainted.
  Verified on c5: target cards moved from 1,260.7 / 11,083,008.7 to 0 / 11,084,175.8 at the first
  snapshot and then to 182 / 11,084,018.8, while best stayed flat and accepted rose. Shell assets
  move to `v55`. Dashboard **GREEN**.

- P30.2: the target editor now shows and writes `normalization`, `priority`, and `notes`, displays
  the derived `kind`, and keeps `kind` out of the YAML. Each target has a compact detail line; the
  Save targets and solve controls are sticky at the bottom of the sidebar. The backend carries
  `kind` in the JSON rows and strips it on save; tests cover the round-trip. Shell assets move to
  `v56`. Dashboard **GREEN**.

- P30.3: the Reports tab now shows an ending-inventory card from `summary.json` (final feature values,
  year, and flow-target status) and lists `ending_inventory.csv` as a standard report. The Compare
  tab adds an ending-inventory table for A/B/delta and a `kind` column in the target table. The report
  tables render before the slower comparison-map request, so a large AOI no longer delays them.
  Verified on c5 with a new 10-iteration run: Reports showed 35 final feature values at year 50; the
  Compare tables rendered while the map was still loading. Shell assets move to `v59`. Dashboard
  **GREEN**.

- P30.4: legacy runs whose `account_values.csv` uses `year` and whose `schedule.csv` uses `period`
  now read through an `offset` alias in the shared table reader. The existing year label is kept;
  current-schema runs still show `offset + 1`. This fixes the Accounts, Periods, Targets, treatment
  map, and used-road readers for old c5 runs instead of returning 500s. An endpoint test builds a
  legacy run and checks accounts, periods, targets, and the treatment map. Dashboard **GREEN**.

- P30 close-out: live snapshots, the complete target editor, ending-inventory/flow surfaces, and
  legacy year/period handling are implemented, tested, documented, and queued in
  `notes/reports/p30-closeout.md` (PR #256, evidence head `d7d949c`). Dashboard **GREEN**.

- P31.1: the Compare map now uses one MVT tile per viewport with a `compare` property (`a`, `b`,
  `both`, or `none`) and `compare-stats` for full-run counts; it no longer fetches both full GeoJSON
  viewports. The vector paint maps A-only red, B-only blue, both purple, and untreated blocks at low
  opacity; block details use the tile's compare flag. Added backend tests for the counts and tile
  flags. Shell assets move to `v61`. Dashboard **GREEN**.
- P32.1: datasets may carry a `data_quality.yaml` provenance sidecar. `ws4 quality` reports it,
  writes JSON/Markdown, and `--check` fails when provenance is missing or the report is not ok.
- P32.2: applied the TSA 46 and TSA 47 provenance records to the current matrices. Both report
  `status: ok` with inventory vintage 2025, VDYP-transform curve provenance, predecessor-derived
  THLB, and explicit null imputation/coverage fields. Recorded in `notes/reference/gbr-provenance.md`.
- P32.3: the limitations page now covers priority tiers, the bounded exact lane, dataset provenance,
  and the GBR VDYP/THLB caveats. Dashboard **GREEN**.
- P32.1-P32.3 refresh: the example notebooks' stored summaries include `provenance_supplied`.
  `python scripts/check_notebooks.py` reports 47 compared, 0 drifted.

- P33.1: added a read-only Search tab that discovers `portfolio.json`, `tuning.json`, and `lp.json`
  under the runs root, renders portfolio members with the Pareto front, and renders tuner ranking
  and parameters. `GET /api/search` and `GET /api/search/{name}` back it; every skin now includes the
  search panel. c5's demo portfolio and tuner artifacts render; the tab points at the CLI commands
  for creating new artifacts. Shell assets move to `v63`. Dashboard **GREEN**.

- P34.1: the Search tab can launch a portfolio or tuner through `POST /api/search/portfolio`
  and `POST /api/search/tune` (gated by `--allow-runs`), poll
  `GET /api/search/{name}/status`, and open the finished artifact. The endpoint composes the existing
  `scripts/portfolio.py` and `scripts/tune.py` with the configured dataset and targets; the tuner
  space is written beside the output. Shell assets move to `v64`. Dashboard **GREEN**.

- P36.1: both GBR instance repositories track `config/dataset_quality.yaml` and provide
  `scripts/apply_dataset_quality.py`; tests cover valid, missing, and CLI cases.
- P35.2: both instance model-build docs link the ws4 limitations page and the VDYP/THLB caveats.
- P35.3: both full build scripts copy the sidecar after `ws4 build` and fail on
  `ws4 quality --check`. Instance PRs #25/#26 merged.
- P35.1: reconciled the P30-P34 planning surfaces. P34 was reopened because P34.2 is
  still planned; P34.2 #272 is now a linked child. P30/P31/P33/P34 issue bodies were
  expanded to the phase/task templates and closed tasks carry completion metadata.
  Added P31 and P33 close-out reports, updated the P30 report to merged, and set P33
  complete. Dashboard **GREEN**.

- P35 close-out: the P30-P34 planning surfaces are reconciled, P34 is active with P34.2 planned,
  and P31/P33 reports are present. Queued in `notes/reports/p35-closeout.md`; dashboard and CI green.

- P36 close-out: pull request #277 squash-merged as `3c07917`; parent #273 and task #274 closed.
  P36 status set complete. P34 remains active for P34.2.
- P37.1: `ws4 quality --sidecar PATH` installs a tracked provenance record beside the matrix
  and keeps the `--check` gate. Dashboard **GREEN**.

- P37.1: `ws4 quality --sidecar PATH` installs a tracked provenance record beside the matrix and
  keeps the `--check` gate.
- P37.2: the `femic.ws4_quality` FreshForge provider builds the install/check command; provider
  metadata and the exact command are covered.
- P37.3: both GBR FreshForge workflows run the quality node after validation, install the sidecar,
  and fail on invalid provenance. Dashboards green.

- P34.2: added `POST /api/search/{name}/stop`, which terminates the search process group and
  reports `stopping`/`stopped`; the in-memory job list is bounded to 20 and drops the oldest
  finished entries. The Search tab shows running jobs and a Stop control. Tests cover stop,
  stopped status, and the bound. Shell assets move to `v65`. Dashboard **GREEN**.

- P34 close-out: pull request #286 squash-merged as `9cdae7`; parent #265 and task #272 closed.
  P34 status set complete.
- P38.1/P38.2: both instances package a `tsaXX.ws4` FreshForge provider with build, validate,
  baseline-schedule, and simulate nodes, entry points, and command tests.
- P38.3: both workflows resolve every node with zero provider diagnostics against the local
  FEMIC provider; instance dashboards are green. The full graph execution smoke remains P39.

- P39.1: account leaves show the full name, the search box reports matched/total counts,
  Enter selects the first match, and arrow keys move between leaves. Period labels are year
  ranges and target rows say "Target period", separating the optimizer clock from the map
  clock. Shell assets move to `v66`. Dashboard **GREEN**.

- P39 close-out: pull request #296 squash-merged as `8f77a9a`; parent #293 and task #294 closed.
  P39 status set complete.

- P40.1/P40.3: both instances add a bounded smoke workflow and
  `scripts/run_provider_smoke.py`, plus docs for the dry-run/real command.
- P40.2: both graphs execute validate → provenance → baseline schedule → one-year simulate with
  every node `success`; evidence is written to `runtime/smoke/evidence.json`. Instance PRs
  #29/#30 merged.

- P41.1: both instances add a tiny provider-smoke fixture and a CI workflow covering build,
  validate, provenance, schedule, and simulate.
- P41.2: `requirements-freshforge.txt` pins the FEMIC/ws4 commits; a separate `Provider smoke` CI
  job runs the graph.
- P41.3: the evidence JSON is uploaded as a CI artifact; both provider-smoke jobs pass.

- P47.1/P47.2: both GBR instances add an accepted model-boundary ADR, a `limitations` docs page,
  and links from the index, model-build guide, and decisions page.
- P47.3: the instance provenance sidecars now name the TSR-consistent BatchTIPSY managed curves,
  keep the VDYP-transform run as a backup, and carry the instance limitations URL and the
  deterministic-seed caveat. The ws4 GBR provenance reference and limitations guide are updated
  to match.
- P42.1: the account tree has a Multi-select mode; one shared target form adds one row per
  selected account in a single `POST /api/targets.json`. The picker shows the selection count,
  mixed/level/flow kind, and a Clear control.
- P42.2: browser-side validation refuses duplicate account/period targets, missing bounds,
  min above max, and invalid priorities before the request. A successful save copies the
  previous YAML to `targets.yaml.bak`. c5 verified: two accounts added in one POST, rows 2→4,
  duplicate blocked, backup written. Shell assets move to `v67`. Dashboard **GREEN**.

- P42 close-out: pull request #315 squash-merged as `cc59a0e`; parent #308 and tasks #309/#310
  closed. P42 status set complete.
- P48.1/P48.2: both GBR instances reconcile the FAIB/Nemora sample, publish a stratified
  ground-plot page with volume, DBH, height, and stems by sample type, species, and age class,
  and add a reproducible summary script and CSV. TSA 46 has 20 matched rows from 17 sites; TSA 47
  has 506 rows from 130 sites, including 480 VRI audits and 26 managed/young rows.
- P48.3: ADR 0002 retains the production TSR-consistent BatchTIPSY curves. TSA 46 is too sparse
  and too old for a correction; TSA 47 shows a real but confounded underprediction. No curve or
  AAC change. The limitations pages and sidecars name the result.

- P43.1: search artifacts expose artifact-relative member paths and a safe file endpoint; the
  Search tab shows member factors/metrics/status and links for schedule, targets, front.csv,
  portfolio.md, and console.log. Traversal outside the artifact is refused.
- P43.2: `lp_sensitivity.json` is discovered and rendered as target duals plus an option
  reduced-cost table, labelled advisory.
- P43.3: portfolio/tuner summaries include failure counts, member/candidate status and error text,
  and console links. c5 verified member downloads and LP rendering; shell `v68`. Dashboard **GREEN**.

- P43 close-out: pull request #334 squash-merged as `7f66e5b`; parent #330 and tasks #331/#332/#333
  closed. P43 status set complete.
- P49.1/P49.2: both GBR instances inventory the public FAIB candidates, add a pre-registered
  four-strata managed/young validation plan, and publish the candidate counts and field audit.
  TSA 46 has 205 candidate sites / 460 visits; TSA 47 has 351 / 572. The public schema has no
  management-origin field.
- P49.3: ADR 0003 records the data limit: the remeasured candidates are natural, experimental,
  or origin-unknown, and zero sites meet the pre-registered minimum. Production TSR curves and
  the AAC remain unchanged. The limitations pages and sidecars name the gap.

- P50.1/P50.2: both GBR production matrices now carry the tracked provenance sidecar, and
  `ws4 quality --check` exits zero (status ok, 12 tables, no warnings). The pre-refresh matrices
  had no `data_quality.yaml`.
- P50.3: both instances publish a runtime-provenance page and tracked hash report with matrix,
  sidecar, manifest, and quality-report hashes. No matrix table, curve, target, or AAC change.
- P44.1: comparison tiles now use a durable disk cache keyed by run pair, period, and tile;
  `prewarm_tiles.py` accepts `compare` and `--compare-against`. Tests cover the disk hit and
  compare pre-warm.
- P44.2: added `scripts/check_compare_browser.py`; it selects a run pair, asserts compare tiles,
  the A/B/both counts, and the Kind column.
- P44.3: added `scripts/benchmark_compare.py` with cold/warm first-tile budgets. c5, six z9 tiles:
  2.063 s cold first, 0.003 s warm first, 13.336 s full cold, 0.018 s warm. Dashboard **GREEN**.


- P44 close-out: pull request #349 squash-merged as `05c3b44`; parent #341 and tasks #342/#343/#344
  closed. P44 status set complete.

- P52.1: added `ws4.io.lidar` to pin FEMIC LidarBC bundles, validate manifest
  schema, OGL-BC licence, checksums, CRS, resolution, vertical datum, and
  source-tile membership, and summarize slope/CHM rasters over polygon support.
  Added the `ws4[lidar]` optional extra, contract note, reference docs, and
  shared parity evidence against `lidarbc-995fb1f771f4d7fe` (max difference
  0.0 versus FHOPS).

- P52.2: added dataset-level FEMIC LidarBC registration. The pin is written to `manifest.json` metadata and `lidar_products.json`; `ws4 lidar register|inspect|validate` and `ws4 build --lidar-bundle` support the operator workflow. Failure fixtures cover missing datasets, wrong pins, and tampered bundles.

- P52.3: added `map_femic_lidar_to_fragments` and `write_lidar_mapping`. Fragment support uses each fragment polygon; block support uses the dissolved block geometry. Outputs include fragment/block CSVs and a manifest with the bundle pin, checksums, CRS, native resolution, statistics, and aggregation rules. Added `ws4 lidar map` and coverage for missing products and CRS mismatch.

- P52.4: added `map_femic_canopy_to_fragments` and `write_canopy_mapping`. CHM mean/p90/p95/max and 2/5/10 m cover map to fragment and dissolved-block support; optional VRI overlap adds area-weighted height/closure and uncertainty deltas; optional bundle tree products add tree counts, height mean/p95, and species counts. Added `ws4 lidar canopy` and tests for VRI/tree mapping and CRS failure.

- P52.5: added `integrate_lidar_mapping_into_dataset` and `ws4 lidar integrate`. Mapping fields are written as optional `lidar_`-prefixed columns in fragment/block Parquet tables; the manifest records bundle pin, mapping hashes, field lists, support keys, and integration timestamp. Datasets without LiDAR fields remain valid; the simulator loads expanded tables unchanged. Re-integration requires `--overwrite`. A 50,000-fragment / 5,000-block synthetic integration with four fields completed in about 0.14 s; no simulator/optimizer code path changes.

- P52.6: ran the real TFL 6 end-to-end consumer path on 7 fragments/1 block using `lidarbc-995fb1f771f4d7fe`. Register, map, integrate, validate, and simulator load all passed. WS4/FHOPS parity was `0.0`; WS4/FEMIC parity was `7.1e-15` (tolerance `1e-9`). Map `0.755 s`, integration `0.037 s`, bundle 13.4 MB, mapping 4.4 KB, dataset 52 KB, licence OGL-BC. Close-out report and metrics added; phase status set `pr-open`.

- P52 close-out: pull request #381 squash-merged as `bd3bc18`; parent #317 and tasks #318/#319/#320/#321/#322/#323 closed. P52 status set complete.
- P51.1/P51.2: clean-checkout verification at `f30cd5b` passes; the dashboard is green; the
  sdist and wheel build and pass `twine check`; both install in isolated environments; both
  entry points and a synthetic build/validate/simulate/report smoke pass.
- P51.3: docs/Pages return 200; version metadata is consistently `0.1.0`, but `v0.1.0` is already
  tagged at `d8ecd72` and released on 2026-10-15. The candidate is green but **not tag-ready**
  until a new version and release notes are approved. No tag or release was created.

- P45.1: added `scripts/profile_route.py` and profiled the c5 production route config on a
  32-block schedule. Full route evaluation is 0.451 s/evaluation; `simulate` is the hot path
  (0.407 s), not route assignment. Wrote `notes/design/ws4-incremental-route.md` with the
  incremental aggregate design, the fallback cases (delivery, planned-network opening, other
  route accounts), seven invariants, and the parity test plan. No incremental code landed.
  Dashboard **GREEN**.
- P45 close-out: pull request #370 squash-merged as `6e49f12`; parent #368 and task #369 closed.
  P45 status set complete.
- P53.1/P53.2: bump the package and citation metadata to `0.2.0`, add the 0.2.0 release notes,
  and replace the deprecated license classifier with the SPDX `Apache-2.0` expression.
- P53.3: clean-checkout, dashboard, sdist/wheel build, `twine check`, isolated installs, entry
  points, synthetic smoke, and Pages checks pass on the 0.2.0 head. No tag or release was created;
  tag approval is pending.


- P46.1/P46.2: added `Simulator.block_route_events`, a per-(block, chain) optimizer event
  cache, and an exact ledger replay for build/maintenance. The replay preserves the full
  simulation's year, schedule-row, and event order. Delivery targets and `initial_roads:
  existing` still take the full path. Parity is within `1.9e-8` on c5; fixture tests cover
  shared-segment build-once, maintenance, both schedule orders, and both fallbacks.
- P46.3: added `scripts/benchmark_route_events.py`. c5, 32 blocks, 64 events: full 0.303 s,
  warm cached 0.037 s (8.25x), cold cached 1.789 s. No GBR route configuration exists in
  the workspace, so the GBR half is recorded as a deviation rather than fabricated.
  Dashboard **GREEN**.

- P46 close-out: pull request #386 squash-merged as `6c31d49`; parent #382 and tasks #383/#384/#385
  closed. P46 status set complete. The GBR benchmark deviation is recorded in the close-out:
  no production GBR route configuration exists in the workspace.

- P56.1: added the read-only `femic.disturbance.v1` consumer (`ws4/disturbance.py`)
  and `ws4 disturbance --events ... [--json] [--block-id ...]`. It loads the flat
  FEMIC consumer rows or full event records, validates the fields ws4 needs, and
  reports counts, types, years, severity classes, affected blocks/fragments, and
  area. 13 unit tests and 4 CLI tests pass. No compiled-dataset, simulator, or
  optimizer behavior changes.

- P56 close-out: pull request #398 squash-merged as `5ea4a05`; parent #393 and task #394
  closed. The read-only `femic.disturbance.v1` consumer and `ws4 disturbance` command
  are in `main`; dashboard and all CI checks were green. No compiled-dataset,
  simulator, or optimizer behavior changed.

- P57.1: added the read-only FEMIC hydrology response-bundle consumer contract in
  `ws4/io/hydrology.py`. It validates `femic.hydrology.response.v1`, required
  and optional artifact roles, role schemas, path containment, declared size and
  SHA-256, response-surface and flood-risk summaries, domain/ledger IDs, and the
  producer consumer contract. Added a stable `bundle_pin`, typed flood-risk
  rows, `ws4 hydrology inspect|validate`, a synthetic contract fixture, the
  design note, and reference docs. Validation is stdlib-only and never contacts
  FEMIC or the network. Producer `consumer_phases` labels (`ws4: P49`,
  `fhops: P14`) are documented as producer metadata, not WS4/FHOPS phase
  numbers. A FEMIC-built fixture bundle (`hydro-response-70f4214e01afe461`)
  validated and inspected successfully through the WS4 CLI. Dashboard **GREEN**
  (lint, format, types, 109.06 s tests, validator, docs, docstrings).

- P57.2: added dataset-level registration for FEMIC hydrology bundles.
  `register_femic_hydrology_bundle` writes the pin to `metadata.hydrology_products`
  and `hydrology_products.json` and references the bundle without copying it.
  `read_registered_femic_hydrology`, `load_registered_femic_hydrology_bundle`,
  and `validate_registered_femic_hydrology` revalidate bundle id/version,
  manifest SHA-256, and artifact sizes/checksums. Added
  `ws4 hydrology register` and `--dataset` modes for `inspect|validate`.
  Seven new tests cover idempotent registration, relative/external references,
  tampering, stale manifests, missing datasets, and CLI success/failure.
  Dashboard **GREEN** (lint, format, types, 111.09 s tests, validator, docs,
  docstrings).

- P57.3: added explicit WS4-to-FEMIC support mapping. A reviewed crosswalk CSV
  names one `fragment_id` or `block_id` per row and a FEMIC unit, watershed, and
  optional receptor. Block rows expand to fragments; block mappings are derived
  from fragment rows only when every fragment is mapped and agrees. Mapping
  validates dataset/FEMIC IDs, rejects conflicts, and writes
  `hydrology_fragments.csv`, `hydrology_blocks.csv`, and a deterministic
  `hydrology_mapping.json` with bundle pin, crosswalk checksum, review status,
  coverage, warnings, and caveats. Added `ws4 hydrology map` and
  `--allow-partial`. No spatial inference, geometry join, or FEMIC re-run.
  Eight new tests cover complete/partial mapping, derivation, conflicts,
  unknown IDs, duplicate/bad rows, review metadata, and CLI behavior.
  Dashboard **GREEN** (lint, format, types, 106.01 s tests, validator, docs,
  docstrings).

- P57.4: added read-only schedule-level flood-risk screening. `ws4 hydrology
  screen` loads a schedule, mapping, pinned bundle, response scenarios, and
  flood-risk rows; derives cumulative harvest fraction by watershed/period;
  selects the nearest response scenario within a tolerance; and writes
  `hydrology_screen.csv` plus a deterministic manifest. Missing scenario
  features, missing watershed areas, and out-of-tolerance schedules refuse.
  `--allow-refused` writes inside-domain rows and records refusals. No
  simulator, optimizer, objective, or FEMIC process is invoked. Seven new tests
  cover complete screening, refusal/allow, missing area, unknown blocks,
  mapping round-trip, bundle mismatch, and CLI output. Dashboard **GREEN**
  (lint, format, types, 106.53 s tests, validator, docs, docstrings).

- P57.5: added optional `flood.*` accounts to the optimizer objective.
  `ws4.hydrology.flood_screen.v1` config names the mapping, global covariates,
  scenario tolerance, and refusal penalty. `FloodRiskModel` appends ratio, peak
  flow, exceedance probability, and expected annual damage rows for each
  receptor/return period; normal targets can price them. Out-of-envelope
  schedules return the configured refusal penalty instead of extrapolating, and
  the move-based delta evaluator is disabled while the model is active.
  `--flood-screen-config` is available on `optimize`, `watch`, and `calibrate`.
  Five new tests cover config loading, account emission, refusal, target
  pricing, and penalty behavior. Dashboard **GREEN** (lint, format, types,
  104.92 s tests, validator, docs, docstrings).

- P57.6: wrote `notes/reports/p57-closeout.md`, recorded the stacked-PR and
  public-pilot deviations, set P57 to `pr-open`, and queued the stack for
  maintainer approval. The hydrology contract suite has 39 passing tests; the
  dashboard is GREEN at the P57.5 evidence head. No merge, tag, release, or
  settings change was made. Known limits: no reviewed public crosswalk, no
  hydrologist review, no independent WS4 tail-check validation, whole-schedule
  flood evaluation, optimizer-only accounts, and no FHOPS integration.
  Report-commit dashboard **GREEN** (lint, format, types, 105.92 s tests,
  validator, docs, docstrings).

- P57 closeout consolidation: retargeted #411 to `main`, recorded the
  maintainer-approved single-phase-PR strategy, and marked the five task PRs as
  superseded. The report now names the squash-merge command and the post-merge
  issue/branch cleanup. No merge has run yet. Consolidation dashboard **GREEN**
  (lint, format, types, 102.98 s tests, validator, docs, docstrings).
  Main advanced with P56/P58 before the phase merge; the closeout branch merged
  `origin/main`, kept both phases, and re-ran the dashboard **GREEN** (lint,
  format, types, 118.57 s tests, validator, docs, docstrings).

- P58 activation: created parent issue #357 and tasks #358-#367 on `feature/p58-carbon`. The phase
  adds the FEMIC carbon-package loader, the CBM SIT compiler, the libcbm driver and `ws4 carbon`,
  carbon accounts and reports, parity and replay validation, a block-level carbon ledger, carbon
  targets in the optimizer, TSA24/MKRF validation, and GCBM output consumption. The design note is
  `notes/design/ws4-carbon.md`. Dashboard **GREEN** (lint, format, types, tests, validator, docs,
  docstrings).

- P58.1: added the carbon package contract loader in `ws4/carbon/package.py`, with a closed
  manifest schema, table/column/unit validation, table hashes, a stable package fingerprint, and
  the exact `track_name` join. Unmatched dataset tracks fail with `CARBON-UNMATCHED-TRACK` unless
  the caller explicitly allows them. Added 16 contract tests over a synthetic package, the
  consumer-side `docs/reference/carbon.rst` page, and the reference-index entry. Dashboard
  **GREEN** (lint, format, types, tests, validator, docs, docstrings).

- P58.2: added `ws4/carbon/sit.py`, which compiles the package, compiled dataset, and schedule
  into SIT classifiers, disturbance types, age classes, inventory, yield, events, and
  transitions. Events take their area from the scheduled block's fragments and set
  `time_step = offset + 1`; treatments map through the package disturbance map. Retention
  splits fail with `CARBON-RETENTION-UNSUPPORTED`. `write_sit_tables` writes the audit copy.
  Eight contract tests cover inventory/event/transition mapping, the package yield grid,
  retention, unknown treatments, unmatched tracks, a missing dataset table, the offset clock,
  and the audit writer; an optional libcbm test parses the tables when the engine is installed.
  The libcbm parse was verified manually against `libcbm==2.10.2`. Dashboard **GREEN**.

- P58.3: added the optional `carbon` extra (`libcbm==2.10.2`), the `ws4/carbon/libcbm.py`
  driver, the `ws4 carbon` command, carbon account summaries, and the run manifest. The
  driver checks the package/defaults hash, builds the libcbm mapping config from the package,
  maps CBM species names directly, and writes pools, fluxes, long tables, accounts, and
  provenance. A real TSA24 package (54 tracks, 6,016,466.4 ha) ran end-to-end against a
  two-fragment dataset: start 232.3 tC, end 212.1 tC over 10 years, all `carbon.*` accounts
  written. Two runs produced byte-identical accounts, pools, flux, and manifest; the audit
  SIT copy was written. Dashboard **GREEN**.

- P58.4: added `merge_carbon_accounts`, the `ws4 carbon --merge-into` option, and a report
  test. Carbon rows are merged into a simulation run's `account_values.csv`,
  `carbon_manifest.json` is copied beside the run, existing `carbon.*` rows are replaced
  idempotently, and non-carbon accounts are preserved. The standard `ws4 report` now carries
  the carbon accounts. Tests cover idempotence and report inclusion.
- P58.5: added `ws4/carbon/parity.py` (frame/run comparison, mass-balance table, byte-level
  replay) and `scripts/carbon_parity.py`. WS3 `tsa24_clipped` and WS4 agree exactly on the
  20-year no-event trajectory (25 inventory rows, 24 yield rows, `max_abs = 0.0` on pools and
  flux). The real TSA24 mini run replays byte-identically and its accounts reconcile to the
  pools. Report: `notes/reports/p585-parity.md`. Dashboard **GREEN**.

- P58.6: added `ws4/carbon/ledger.py`, a block-level carbon ledger keyed by
  `(block, chain)`. It runs one block's CBM chain at a time and sums the blocks; the
  synthetic two-block fixture matches a full-schedule libcbm run exactly (`max_abs = 0.0`).
- P58.7: added `--carbon-package` to `ws4 optimize`, carbon-aware incremental objective
  deltas, the carbon target guard, and carbon accounts in the final run/report plus
  `carbon_ledger.json`. A quickstart smoke with a `carbon.ecosystem.total` ceiling reduced
  the objective from 1003.25 to 887.08 and chose a clearcut on block 1; ecosystem carbon at
  offset 1 fell from 1203.25 to 1087.08 tC. Report:
  `notes/reports/p587-carbon-optimizer.md`. Dashboard **GREEN**.

- P58.8: validated the real TSA24 and MKRF instances. Built the full TSA24 dataset
  (536,458 fragments, 108 tracks) and carbon package (108 tracks, 6,016,466.4 ha); a
  one-AU baseline (7,313 fragments) ran five years in 38 s (21.77M -> 21.95M tC). The full
  536k-fragment run was stopped after 35m30 at ~99% CPU with no output. Carbon-aware search
  on a 50-block TSA24 subset met a 134,000 tC ceiling (objective 0.0, 3 CC blocks; exact
  verification 133,294.95 tC; ledger/exact difference ~0.03%). Built the full MKRF dataset
  (3,183 fragments, 7,048 tracks) and a dataset-derived package (1,903 tracks); a five-block
  subset met a 10,500 tC ceiling (objective 0.0, 2 CC blocks; exact 10,478.44 tC; ledger
  exact). Report: `notes/reports/p588-carbon-validation.md`. Dashboard **GREEN**.

- P58.9: added `ws4/carbon/gcbm.py` and `ws4 gcbm`, reading the GCBM 2.5.x results
  database without FLINT or Wine and mapping pools to `carbon.*` accounts. The supplied
  GCBM package was run under Wine 9.0 on the bundled Standalone Template: 11,347 land units
  in 85 s. The reader produced 120 locations / 12 steps and 67,388.5 -> 52,880.9 tC.
  `compare_gcbm_to_carbon` and `--compare-carbon` are ready; a same-landscape TSA24/MKRF
  comparison is deferred until the FEMIC walltowall export (P115.4). Report:
  `notes/reports/p589-gcbm-results.md`. Dashboard **GREEN**.

- P58.10: completed the phase closeout. The closeout report is
  `notes/reports/p58-closeout.md`; the roadmap status is `complete` and pull request #408
  was squash-merged as `ddf4ed8`. Remaining deferred
  items are the full TSA24 landscape search, the same-landscape GCBM comparison (needs
  P115.4), species-resolved curves/crosswalk review, and CBM4. Dashboard **GREEN**.

- P58 renumbering: the carbon phase was opened as P51 and then P57; both numbers were already
  claimed on `main` or by the active hydrology phase. A follow-up renumbers the carbon phase,
  its reports, roadmap section, and issue labels to P58. No runtime code or evidence changed.

- P57 close-out merged: pull request #411 squash-merged as `75399d3`; the six
  P57 branches were deleted. The phase report is
  `notes/reports/p57-closeout.md`, and P57 is marked complete. Child issues and
  parent #395 are closed with this merge cited. The next recommendation is a
  public-watershed pilot/tail-check hardening phase, or FHOPS Phase 15 after its
  P14 LidarBC phase merges.

- P55.1: updated the 0.2.0 release notes for the merged P52 LiDAR, P58 carbon, P57 hydrology,
  P56 disturbance, and P46 route-event work; removed the stale "P51/P52 not in 0.2.0" gap; added
  the `lidar` and `carbon` install extras; recorded phase verification evidence and the remaining
  carbon/hydrology/LiDAR limits. Added the Phase 55 roadmap section and tracker row. No tag.

- P55.2: verified the final head with `.[geo,opt,carbon,lidar]` installed. Clean-checkout and
  dashboard pass; added a `libcbm` mypy override and installed the optional extras in the
  quality/dashboard/pre-commit jobs so carbon/LiDAR tests run. sdist/wheel build, `twine check`,
  isolated installs, entry points, carbon/lidar/disturbance/hydrology commands, synthetic smoke,
  and Pages pass.
- P55.3: no tag or release created. Candidate is ready for explicit tag approval.

- P59.1/P59.2: added `/api/lidar`, a canonical LiDAR field catalog and block join, a LiDAR tab with
  provenance/field selection/range legend, map colouring, and block-detail values. The LiDAR layer
  uses the explicit GeoJSON join rather than MVT; datasets without LiDAR keep an explicit disabled
  state. Fixed the P52 overwrite path so re-integration drops canonical and `_x`/`_y` variants
  before joining.
- P59.3: re-integrated the real TFL 6 7-fragment/1-block validation dataset with six canonical
  fields (slope and CHM valid-pixels/mean/p95), ran `scripts/check_lidar_browser.py` (exit 0), and
  verified c5 reports no LiDAR. Dashboard **GREEN**.

- P59 close-out: pull request #425 squash-merged as `1d1bb2a`; parent #417 and tasks
  #418/#419/#420 closed; status set complete. The P52 overwrite repair and the real TFL 6
  LiDAR UI smoke are recorded in `notes/reports/p59-closeout.md`.

- P60.1: added FEMIC validation-evidence readiness reporting.
  `assess_femic_hydrology_readiness` reads optional `validation_report` and
  `model_card` artifacts and reports `not_available`, `provisional`,
  `conditionally_ready`, `ready`, or `blocked`, with review status, usable fits,
  tail-check failures, benchmark counts, and a deterministic evidence digest.
  Added `ws4 hydrology readiness` for direct bundles and registered datasets.
  Missing evidence is never treated as approval; tail failures always block.
  Eight new tests cover missing, provisional, blocked, reviewed, conditional,
  malformed/mismatched, deterministic, and CLI paths. Dashboard **GREEN**
  (lint, format, types, 121.43 s tests, validator, docs, docstrings).

- P60.2: added readiness gating for hydrology screening and optimization.
  `enforce_hydrology_readiness` implements `allow_provisional`,
  `require_reviewed`, and `require_ready`; tail-check blocks refuse under every
  policy, with `allow_tail_failures` as an explicit `allow_provisional`-only
  override. `ws4 hydrology screen` checks the policy before reading the
  schedule. `FloodRiskModel` checks it at construction, so an optimizer run
  fails early instead of returning refusal penalties for every schedule. Added
  `readiness_policy`/`allow_tail_failures` to the flood-screen config and four
  policy/CLI/optimizer tests. Dashboard **GREEN** (lint, format, types,
  121.59 s tests, validator, docs, docstrings).

- P60.3: wrote `notes/reports/p60-closeout.md`, recorded the P59-to-P60
  renumbering collision with the LiDAR UI PR #425, consolidated P60 into a
  single phase PR #428, and set P60 to `pr-open`. The hydrology contract suite has 51
  passing tests; the dashboard is GREEN at the P60.2 evidence head. No merge,
  tag, release, or settings change was made. Report-commit dashboard **GREEN**
  (lint, format, types, 113.80 s tests, validator, docs, docstrings). Main
  advanced with P55/P59 before the phase merge; the closeout branch merged
  `origin/main`, kept all phases, and re-ran the dashboard **GREEN** (lint,
  format, types, 112.04 s tests, validator, docs, docstrings).

- P60 close-out merged: pull request #428 squash-merged as `b2012bd`; the
  P60/P59 task branches were deleted. P60 was renumbered from P59 after the
  LiDAR UI phase claimed P59. The phase report is
  `notes/reports/p60-closeout.md`; child issues and parent #415 are closed.
  Next recommendation: public-watershed pilot/tail-check remediation, or FHOPS
  Phase 15 after P14. Post-merge dashboard **GREEN** (lint, format, types,
  123.47 s tests, validator, docs, docstrings).
- 0.2.0 published to PyPI: `ws4==0.2.0` is available at https://pypi.org/project/ws4/0.2.0/.
  The published wheel and sdist match the GitHub release assets. The release policy now records
  that approved PyPI releases use a secure external credential file.


- P61.1/P61.2: added `/api/runs/{run}/carbon`, carbon-only run discovery, carbon-account and period
  fallbacks, and a Carbon tab with provenance, account trend, pool composition, ledger status,
  GCBM comparison table, and artifact downloads. The service aggregates libcbm pools/fluxes by
  timestep and never reruns carbon.
- P61.3: verified TSA24 and MKRF real carbon artifacts. API account series match the CSVs at
  `max_abs = 0.0`; browser smoke exits 0 for the standalone and optimizer runs; c5 shows the
  explicit no-carbon state. No real `gcbm_compare.csv` exists, so that UI branch is fixture-tested.
  Dashboard **GREEN**.

- P61 close-out: pull request #436 squash-merged as `b61224a`; parent #430 and tasks
  #431/#432/#433 closed; status set complete. Carbon/libcbm evidence and the GCBM
  comparison gap are recorded in `notes/reports/p61-closeout.md`.

- P63.1-P63.3: rebuilt the web shell around Map, Plan, Results, and Data workspaces, moved
  Reports/Compare/Search and Dataset/LiDAR/Carbon into nested navigation, made the sidebar and
  header fit 1024-1500 px landscape, added WAI-ARIA tab semantics/keyboard movement/URL state,
  a dataset panel, capability-aware Data options, and a map/run loading overlay. Phone layouts
  are explicitly out of scope; iPad Pro landscape is the supported small surface.
- P63.4: added `scripts/check_ui_shell.py` and verified 1024×768, 1194×834, 1366×1024, and
  1500×1000 with no horizontal page scroll and usable map widths. LiDAR, carbon, compare, and
  target browser smokes pass. Dashboard **GREEN**.

- P63 close-out: pull request #447 squash-merged as `63a39ef`; parent #442 and tasks
  #443/#444/#445/#446 closed; status set complete. The four-workspace shell, URL/keyboard
  navigation, Data sub-navigation, and iPad landscape evidence are recorded in
  `notes/reports/p63-closeout.md`.

## 2026-10-26

- P62.1: re-scoped P62 from a Chapman/Seymour watershed pilot to a bounded
  hydrology consumer-hardening phase. Rewrote parent issue #437, added the
  Phase 62 roadmap section and issue-tracker row, created P62.1-P62.6
  (#449-#454), and wrote `notes/design/ws4-hydrology-consumer-hardening.md`.
  Chapman remains closed/data-blocked; Seymour remains an upstream dependency on
  FEMIC #388. No production code and no watershed result. Dashboard: **GREEN**.

- P62.2: added `ws4 hydrology preflight` and
  `ws4.hydrology.preflight.v1`. The report combines bundle pin, readiness,
  policy, crosswalk review, and mapping coverage, defaults to
  `require_reviewed`, and exits non-zero when `screening_ready` is false. A
  missing crosswalk is always blocking; `--allow-partial` remains diagnostic.
  Added unit/CLI tests and reference docs. Dashboard **GREEN**.

- P62.3: added `ws4.hydrology.exposure.v1` and
  `ws4.io.hydrology_exposure`. The loader requires a complete declared
  watershed/period grid, non-negative finite road lengths, non-negative integer
  culvert counts, explicit review metadata, and a 64-character schedule hash.
  It preserves the file SHA-256 and performs no spatial inference. Added the
  synthetic exposure fixture, tests, design note, and reference docs. Dashboard
  **GREEN**.

- P62.4: wired the explicit exposure table into one-schedule screening.
  `hydrology screen --exposure` checks the schedule hash, rejects overlapping
  global covariates, refuses missing watershed/period rows, and records the
  exposure ID/digest/review state. Raw features and calculated densities enter
  response-scenario selection and the row CSV. The optimizer refuses a
  flood-screen config that names exposure until schedule-derived exposure can be
  evaluated per candidate. Added tests, docs, design note, and backlog entry.
  Dashboard **GREEN**.

- P62.5: added `tests/test_hydrology_integration.py` with a synthetic
  bundle/dataset/crosswalk/schedule-bound-exposure fixture. The success path
  runs `validate`, `readiness`, `preflight`, `map`, and `screen` through the
  CLI and checks the exposure identity, manifest, and row CSV. The fail-closed
  matrix covers tail-check block, unreviewed crosswalk, partial mapping, missing
  required exposure, schedule-hash mismatch, and optimizer refusal. Updated the
  design note and reference docs. Dashboard **GREEN**.
- P64.1/P64.2: added `/api/runs/{run}/target-series` and a Plan-space target chart canvas.
  Charts group target rows by account and show all run periods with red minimum, blue maximum,
  grey acceptable band, black achieved line, exact hover/selected-period readout, and an
  expandable all-period table. Inactive targets chart as indicators; live SSE snapshots update
  achieved values in place. The target table remains the editor.
- P64.3: verified c5 (2 charts/5 periods) and TSA 46 (2 charts/10 periods, 21 bounds), inactive
  targets (2 inactive cards), and a 400-iteration live c5 run whose achieved value moved
  1,260.74 -> 26,077.22 -> 35,150.61 without reload. `check_target_charts.py` exits 0; iPad
  1024 and desktop 1500 have no page overflow. Dashboard **GREEN**.

- P64 close-out: pull request #461 squash-merged as `8b0d0e6`; parent #456 and tasks
  #457/#458/#459 closed; status set complete. The chart/live-convergence evidence is
  recorded in `notes/reports/p64-closeout.md`.

- P62.6: ran the hydrology integration/contract/exposure/preflight suites and
  the full dashboard after merging `origin/main` at `0be35ad`. Wrote
  `notes/reports/p62-closeout.md`, set Phase 62 to `pr-open`, and queued the
  single phase pull request #468 for approval. CI run 40397685253 passed all
  jobs. No merge, tag, release, or settings change was made. Dashboard
  **GREEN**.

- P65.1/P65.2: made the target charts editable. The chart now reconciles a period to its target
  row, creates missing rows from account defaults, supports active/inactive toggles, exact min/max
  entry, vertical drag, per-period or all-period application, clear-bound, dirty state, and save
  through the existing validated targets JSON. Source-cell, target-row, chart, and target-table
  updates stay in sync after save.
- P65.3: verified c5 single-period edit/save/reload, all-period min creation, drag edit, and
  inactive toggle; verified TSA 46 10-period edit/save/reload. `check_target_editing.py` exits 0.
  Dashboard **GREEN**.

- P65 close-out: pull request #469 squash-merged as `342ac3b`; parent #464 and tasks
  #465/#466/#467 closed; status set complete. The edit/save/reload evidence is recorded in
  `notes/reports/p65-closeout.md`.

- P62 close-out: pull request #468 squash-merged as `55f7fdf`; parent #437
  and tasks #449/#450/#451/#452/#453/#454 closed; status set complete. The
  preflight, explicit exposure contract, schedule-bound screening, optimizer
  refusal, and synthetic integration evidence are recorded in
  `notes/reports/p62-closeout.md`. Dashboard **GREEN**; final pre-merge CI run
  `40407187849` passed all five jobs.

- P66.1: hid the assistant panel and splitter unless `/api/agent` reports both enabled and
  available. A service without `--allow-agent` gives the sidebar back the full vertical space;
  an enabled service keeps the resizable panel. Version `v74`.

- P54 roadmap entry: added the Phase 54 parent (#375) for environmental accounts
  (DHI, structure habitat, resilience metrics), with children #376-#378. The
  phase excludes carbon, which is owned by P51 (#357). Branch
  `feature/p54-environmental-accounts`; planning note
  `notes/p54-environmental-accounts.md`. No model or objective change.

- P54.1: added the Dynamic Habitat Index biodiversity account.
  `ws4 dhi ingest` samples one published DHI raster at block polygons, refuses a
  block with no valid pixel, and writes `dhi_values.csv` plus a versioned
  `dhi_metadata.json` (product, version, year range, CRS, scale, bbox, valid
  pixels, licence, SHA-256). The account is `feature.DHI.<band>` (level,
  `index_ha`), `feature.DHI.<band>.mean` (level, `index`), and
  `feature.DHI.area` (level, `ha`); a treated block leaves the account for the
  rest of the run. `ws4 simulate --dhi-values/--dhi-metadata` records the
  trajectory and preserves the run-local provenance; `ws4 report` adds
  `report_dhi.csv` with the scale/interpretation caveat. `GET
  /api/runs/{run}/dhi` returns the values, and `?format=geojson` joins them to
  block geometry as the web layer. The pilot uses a real SILVIS MODIS 6.1 Terra
  NDVI 2003-2022 500 m subset; the four blocks are synthetic. Two schedules show
  the surviving DHI area move from 40 ha to 20 ha. Tests cover coverage,
  missing source version, every-block coverage, reproducibility, both
  schedules, the report caveat, and the GeoJSON layer. Report:
  `notes/reports/p54.1-dhi-account.md`.
  Verification: `python -m pytest tests/test_dhi.py -q --no-cov` -> 10 passed;
  `python scripts/dashboard.py` -> **GREEN** (lint 0.07 s, format 0.09 s,
  types 0.82 s, tests 159.11 s, validator 0.90 s, docs 4.82 s,
  docstrings 4.34 s).

- P54.2: added the published Coops et al. (2016) forest structure habitat index.
  The exact definition is P95 first-return height, percentage of first returns
  above 1.37 m, and the SD of first-return heights above 1.37 m, with breaks at
  10/20 m, 33/66%, and 3/5 m. The paper has no weights; WS4 records the
  equal-component statement instead of inventing coefficients. `ws4 shi ingest`
  writes a stand table and versioned metadata; `ws4 shi diagnose` reports
  present, missing, and proxy metrics without substitution; `ws4 shi compare`
  reports Pearson/Spearman agreement with DHI bands and records disagreement.
  `ws4 simulate --structure-values/--structure-metadata` records
  `feature.SHI.height`, `.cover`, `.complexity`, `.area`, and component class
  areas; `ws4 report` adds `report_structure_habitat.csv` with the caveat. The
  synthetic four-block fixture moves from 40 ha to 20 ha under the harvest
  schedule; the real TFL 6 FEMIC bundle reports `index_computable: false`
  because its CHM fields are not the required first-return metrics. Report:
  `notes/reports/p54.2-structure-habitat.md`.
  Verification: `python -m pytest tests/test_structure_habitat.py -q --no-cov`
  -> 11 passed; `python scripts/dashboard.py` -> **GREEN** (lint 0.07 s,
  format 0.09 s, types 7.66 s, tests 170.62 s, validator 0.80 s, docs 19.60 s,
  docstrings 4.45 s).

- P54.3: added descriptive spatial resilience accounts. Connectivity reports the
  largest untreated component, percolation reach, component count, and untreated
  area over the full topology. Age-class diversity reports Shannon, evenness, and
  occupied 20-year classes. Fragmentation reports current-year opening patch
  count, mean/largest patch area, and treated area, reusing the existing patch
  metrics. Connectivity and age are levels; fragmentation is a per-year flow.
  `ws4 simulate --resilience --topology ...` writes `resilience_metrics.csv` and
  `resilience_metadata.json`; `ws4 report` adds `report_resilience.csv`; `ws4
  resilience compare` compares two runs. The sample-estate pilot opens one patch
  (42.9 ha) versus four isolated patches (38.6 ha total); patch count is 1 versus
  4 while age-class count stays 5, so the families are not redundant. No
  objective, constraint, growth, or solver change. Report:
  `notes/reports/p54.3-resilience.md`.
  Verification: `python -m pytest tests/test_resilience.py -q --no-cov` ->
  8 passed; `python scripts/dashboard.py` -> **GREEN** (lint 0.07 s, format
  0.07 s, types 7.14 s, tests 129.22 s, validator 0.68 s, docs 17.69 s,
  docstrings 3.02 s).

- P54 close-out: all three environmental-account children are merged: P54.1
  DHI #463 as `b0438de`, P54.2 structure habitat #471 as `b4f7caa`, and P54.3
  spatial resilience #475 as `865bef6`. Parent #375 and tasks #376/#377/#378 are
  closed. The phase adds `feature.DHI.*`, `feature.SHI.*`, and
  `resilience.*` accounts, report blocks, the DHI web layer, coverage/gap
  diagnostics, and the exact Coops et al. (2016) definition without invented
  weights. No objective, constraint, growth, or solver change. Post-merge
  dashboard **GREEN** (lint 0.10 s, format 0.12 s, types 29.15 s, tests
  134.53 s, validator 0.90 s, docs 17.51 s, docstrings 2.98 s).

- P66 close-out: pull request #476 squash-merged as `ed1f15a`; parent #473 and task #474
  closed; status set complete. The assistant panel is absent when the service has no agent.

- P54 adoption validation: replayed the real North Island compiled estate
  (51,289 blocks, two 31-year schedules) with the DHI account and resilience
  metrics. DHI sampled all 51,289 blocks at 500 m; the corrected BC Albers
  geometry covered 442,452 ha. Baseline and `scenario_retain_low` diverged in
  untreated area (381,092 vs 403,113 ha), largest component (132,005 vs
  144,527 ha), and total opening area (61,360 vs 39,339 ha), while age Shannon
  was nearly unchanged (2.692 vs 2.681). DHI total and mean moved in different
  directions in the baseline, confirming that both are needed. The North Island
  GeoJSON's declared CRS is wrong (4326 metadata on 3005 coordinates); the run
  overrode it. The TFL 6 bundle still cannot compute the published structure
  habitat index because the exact first-return metrics are absent. Report:
  `notes/reports/p54-adoption-northisland.md`. Dashboard **GREEN** (lint
  0.11 s, format 0.09 s, types 31.10 s, tests 153.86 s, validator 0.75 s,
  docs 19.35 s, docstrings 3.83 s). No code or objective change.

- P67.1: fixed target-chart period selection by making each period hit element the pointer
  authority instead of relying only on inverse x-coordinate math. Added a selected-period
  highlight and extended the chart smoke to click the centers of P1, P2, and the last period
  and assert the selected period. c5 `run-base`: centers 0→P1, 1→P2, 20→P21; highlight present.
  Version `v75`.

- P54.2 real TFL 6 point-cloud follow-up: downloaded the two public LidarBC
  OP24BMRS001 2024 LAZ tiles for the TFL 6 1 km AOI (8 points/m², OGL-BC) and
  computed the published Coops et al. (2016) metrics from first returns
  normalized with the FEMIC 1 m DEM. Seven VRI blocks: area-weighted mean height
  22.95 m, cover 69.82%, complexity 6.86 m; five H2-C2-K2, one H1-C0-K2, one
  H2-C0-K2. The FEMIC bundle still exposes CHM products only, so its
  `index_computable: false` result is a materialization gap, not a data-access
  blocker. Added `examples/structure_habitat_tfl6` and updated the structure
  reference page. Dashboard **GREEN** (tests 153.86 s; report-only change).

- P67 close-out: pull request #482 squash-merged as `9ae8f5f`; parent #479 and task #480
  closed; status set complete. Target chart period hit zones and highlight verified.

- P54.2 TFL6 30 m cell support: binned the first returns from the two public
  LidarBC LAZ tiles into 30 m cells after FEMIC DEM normalization. 1,120 valid
  cells, 36 nodata; cell means 20.12 m height, 70.60% cover, 5.92 m complexity;
  700 cells H2-C2-K2. Added the cell table, class raster, metrics raster, block
  class-area table, and block-vs-cell comparison to
  `examples/structure_habitat_tfl6`. Block aggregation hides within-block
  variation: block 16624698 is H2-C0-K2 at block level but 62.3% of its area is
  low height. Report-only change; docs build and validator pass. No objective
  change.

- INV-05 species composition pilot: added `ws4.species` and `ws4 species
  ingest/compare` for a public dominant-species raster. The contract stores
  block/class fractions and a leading species, plus required source version,
  year, CRS, licence, citation, and class map; it does not infer mixedwood
  fractions from a dominant-only layer. The TFL 6 pilot uses the NTEMS 2022
  30 m layer: public classes 0/33/35, western redcedar leading all seven VRI
  blocks, 4/6 comparable blocks agreeing with VRI (66.7%); blocks 16624698 and
  16625195 disagree, and one block has no VRI label. Added
  `examples/species_tfl6` and `docs/reference/species-composition.rst`.
  Verification: `python -m pytest tests/test_species.py -q --no-cov` -> 5
  passed; `python scripts/dashboard.py` -> **GREEN** (lint 0.10 s, format
  0.08 s, types 1.73 s, tests 144.85 s, validator 0.81 s, docs 3.81 s,
  docstrings 3.13 s). No objective change.

- INV-05 species fractions: added `ws4 species fractions` and the
  `ws4.species.fraction.v1` long table. VRI species percentages for the six
  labelled TFL 6 blocks are ingested without normalization or imputation; block
  23339462 has no VRI species rows and is listed as missing. The leading fraction
  ranges 0.40-0.60 and the non-leading fraction is 0.40-0.60, so all six blocks
  are mixed. The public NTEMS dominant layer cannot represent that mixture. Added
  `species_fractions.csv`, summary, metadata, VRI input, and VRI code map to
  `examples/species_tfl6`. Verification: 7 species tests pass; dashboard GREEN
  (lint 0.08 s, format 0.07 s, types 1.18 s, tests 137.86 s, validator 0.84 s,
  docs 3.91 s, docstrings 2.82 s). No objective change.

- P68 map visual hierarchy: pull request #491 squash-merged as `694232d`. Untreated
  blocks use a neutral fill, treated blocks keep the red accent, selection has a dark
  outline in MapLibre and SVG, and an on-map legend carries the layer, counts, and a
  treated-only toggle. Map-engine and unavailable-layer controls are compact disclosures.
  Browser smoke passed on c5 (1,171 treated / 11,396 untreated) and TSA 46 (2,427 /
  167,127); dashboard GREEN. UI `v76`.

- DIS-04 post-fire recovery pilot: added `ws4.recovery` and
  `ws4 recovery ingest` for the public NTEMS post-disturbance recovery-rate
  layer (fire 1986-2012, observation 1985-2017, 30 m, OGL-C). The contract
  reports faster/slower/not-recovered fractions and a dominant status; blocks
  outside the fire footprint are `outside_footprint`, never imputed as failure.
  The real TSA46 5 km pilot has 33 VRI blocks, 31 in the footprint; all 31 are
  dominated by not recovered, with 5,224 ha of burned recovery area. Added
  `examples/recovery_tsa46` and `docs/reference/recovery.rst`. Verification:
  4 recovery tests pass; full dashboard GREEN (tests 130.22 s). No objective
  change.

- DIS-04 TSA23 full-estate recovery: added `--method raster` to `ws4 recovery
  ingest` for full-estate block-id rasterization and bincount. Applied the
  NTEMS fire recovery layer to all 102,128 TSA 23 blocks: 1,555 in footprint,
  1,497 not recovered (21,948 ha, 5,727 ha burned), 58 slower (745 ha), no block
  dominated by faster recovery. The existing 2,000-block baseline schedule has
  29 not-recovered blocks (212 ha) and 2 slower blocks (8 ha). Added
  `examples/recovery_tsa23` and updated `docs/reference/recovery.rst`.
  Verification: 5 recovery tests pass; full dashboard GREEN (tests 131.50 s).
  No objective or constraint change.

- P69 LiDAR and carbon display polish: pull request #500 squash-merged as `1743a04`.
  LiDAR coverage and min/max are dataset-wide, the panel and on-map legend use a
  colour-blind-safe viridis ramp with a missing-value swatch, and carbon accounts
  have human labels, inferred units, labelled axes, and hover/tap tooltips. Empty
  LiDAR/Carbon tabs stay compact. Real FEMIC LiDAR and TSA 46 GCBM checks passed;
  dashboard GREEN; UI `v77`.

- DIS-04 TSA23 deferral scenario: joined the full TSA23 `ft_warm` schedule
  (44,388 blocks) to recovery status and deferred treatments on the 411
  not-recovered scheduled blocks (6,048 ha). Harvested volume moved from
  138.50M to 137.12M m3 (-1.00%) and treated area by -3,579 (-1.13%); deferring
  not-recovered plus slower blocks gives -1.03% volume. The treated-area
  reduction is smaller than block area because some treatments are not
  operable. Added `deferred_blocks.csv`, scenario comparison, and summary to
  `examples/recovery_tsa23`, and updated the recovery docs. No objective or
  constraint change.

- DIS-04 TSA23 deferral window: applied 5- and 10-year treatment shifts to the
  491 not-recovered blocks (7,502 ha) in the full 20-year
  `abatement_bc/sim_6400000000` schedule. Harvested volume moved from 164.42M to
  164.31M m3 (-0.069%) and 164.27M m3 (-0.093%); treated amount fell by 742 and
  1,187. 42 blocks (1,032 ha) fall beyond the horizon under a 5-year shift, 61
  blocks (1,558 ha) under 10 years. The aggregate impact is small, so recovery
  remains an informational overlay rather than a hard constraint. Added
  `deferred_blocks_20y.csv`, window comparison, summary, and report. No
  objective change.

- P70 target-table polish: pull request #508 squash-merged as `cd2b113`. The target
  table now uses compact account labels with root badges, unambiguous inferred units,
  P<n>/All period labels, and inline met/below/above/off status chips that update on
  live runs. Account/period/min/max/status sorting preserves edits and target indices;
  min/max weights moved to the detail row. c5 and TSA 46 checks passed; dashboard GREEN;
  UI `v78`.

- P71 target triage: pull request #516 squash-merged as `fd50042`. Plan now shows a
  failing-first summary above the table and chart canvas, combines account and
  status filters while preserving hidden edits, and can bulk-pin visible failing
  targets or unpin the visible view. c5 and TSA 46 checks passed; dashboard GREEN;
  UI `v79`.

## 2026-10-27

- Carbon documentation audit and HWP/system-carbon pass. Added a WS4 carbon how-to and
  role/source-of-truth map, expanded the carbon reference with HWP lifecycle, simulated-
  clearcut carbon curves, system accounts, complete failure codes, and current production
  evidence. Added `notes/reports/p120-multi-boundary.md` and
  `notes/reports/carbon-docs-audit.md`; corrected the historical carbon design note.
  Added WS4 `ws4/carbon/hwp.py`, `ws4/carbon/curves.py`, `config/carbon/hwp.bc.yaml`,
  `ws4 carbon --hwp-config`, `ws4 optimize --carbon-hwp`, and `ws4 carbon-curves`, with
  tests for the lifecycle, curve helpers, and target guards. Added FEMIC `carbon-overview`,
  `hwp-lifecycle`, `hwp.bc.yaml`, `docs/llms.txt`, and cross-repo links; corrected the
  multi-boundary and fertilization contract text. Verification:
  `python scripts/dashboard.py` -> **GREEN** on all seven gates (lint, format, types, tests,
  validator, docs, docstrings); targeted
  `pytest tests/test_carbon_hwp.py tests/test_carbon_curves.py tests/test_carbon_ledger.py -q --no-cov`
  -> 16 passed; FEMIC `sphinx-build -b html docs _build/html -W` -> build succeeded with no
  warnings.

- P72 Results run health and cross-links: pull request #522 squash-merged as `ba4199c`.
  Results shows a run-health card with target counts, pinned charts, and data availability;
  Open Plan and Show failing targets move into target triage, and Compare target-status
  accounts open the Plan account filter. c5 and TSA 46 checks passed; dashboard GREEN;
  UI `v80`.

- P73 live map updates: pull request #529 squash-merged as `6e3b29b`. MapLibre now
  uses block-id feature state from schedule SSE events while a solver runs, so treated
  blocks, counts, and the map legend update without reloads or per-event tile requests.
  MVT features carry ids and the tile cache is v9. c5 and TSA 46 live-map checks passed;
  dashboard GREEN; UI `v81`.

- P74 live map hardening: pull request #535 squash-merged as `b518324`. The full live
  schedule is reapplied after pan/zoom and source reloads, and a map-legend toggle switches
  between the live schedule and the static pre-run treatment MVT without stopping the solve.
  c5 and TSA 46 live checks passed; dashboard GREEN; UI `v82`.

- P75 live run attach and reconnect: pull request #541 squash-merged as `2abca53`.
  The shell discovers running search runs before they have a summary, attaches to their SSE
  stream after page load or refresh, replays target/schedule snapshots, falls back to target-row
  periods while account values are absent, and shows a LIVE badge. c5 and TSA 46 attach checks
  passed; dashboard GREEN; UI `v83`.

## 2026-10-28

- P76 c5 base scenario: pull request #547 squash-merged as `9ac4136`. Archived 112
  accumulated test-run/scenario entries, kept one baseline run cropped to years 0-199,
  and added a documented 20 x 10-year even-flow base scenario with a 1M/period
  harvest floor and a final growing-stock floor at 90% of initial (23,900,770.58).
  Scenario contract test passes; dashboard GREEN; UI `v83`.

- Carbon ledger performance: added `filter_carbon_package` and a cached per-block
  reachable-track context in `CarbonLedger`. A 500-block TSA46 empty base fell from
  3 h 47 min before iteration 1 to 713 s, and a 20-iteration 500-block max-stock search
  completed in 870 s with 20 iterations. Exact `ws4 carbon` replay agreed with the
  ledger to about 9e-6 relative on the tested schedule; the remaining difference is
  cross-block aggregation in the exact SIT run. Added
  `notes/reports/carbon-ledger-performance.md` and a performance note in
  `docs/reference/performance.rst`. This makes a bounded 500-block search start, but a
  batched/precomputed base is still the next production step.

- P77 c5 even-flow ceiling: pull request #552 squash-merged as `b5b0bae`. The base
  scenario now uses the priced conifer/deciduous accounts (700k/50k per decade,
  ±1% even flow, 90% final stock floor). The max-flow probe completed with an
  advisory ceiling of 0 and no verified positive floor; recorded as a negative
  result, not a certified maximum. Dashboard GREEN; UI `v83`.

- P78 warm c5 max-flow probe: pull request #556 squash-merged as `dc71963`. A
  20,000-iteration, four-probe even-flow run still returned advisory ceiling 0
  with the 90% final stock floor. Recorded as negative evidence; the base scenario
  remains a policy floor, not a certified maximum. Dashboard GREEN; UI `v83`.
