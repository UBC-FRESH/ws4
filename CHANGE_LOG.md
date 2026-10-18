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
