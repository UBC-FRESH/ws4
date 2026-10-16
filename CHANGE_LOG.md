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
- Completed Phase 0: squash-merged pull request #8 as `386c643`, deleted `feature/p0-scope-design`, and
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
- Completed Phase 1: squash-merged pull request #14 as `33ac569`, deleted `feature/p1-contracts-prototype`,
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
- P2 close-out carried out: pull request #25 squash-merged as `3e87d46`, branch `feature/p2-build`
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
- P3 close-out carried out: pull request #35 squash-merged as `83e2d60`, branch `feature/p3-verify`
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
- Completed Phase 4 (Release and deploy): squash-merged pull request #43 as `a06d0ca`, deleted the
  branch `feature/p4-release`, and closed parent issue #36. Created and pushed the annotated tag
  `v0.1.0`, and published the GitHub release `v0.1.0` with the sdist (`ws4-0.1.0.tar.gz`) and the wheel
  (`ws4-0.1.0-py3-none-any.whl`), built from a clean checkout of the tag. Verified the published docs
  site (`https://ubc-fresh.github.io/ws4/`, the Docs workflow run `38785009892` on `main`) and the
  published artifact (P4.6): a fresh virtual environment installed the released wheel, and the `ws4`
  command ran build, validate, simulate, report, and optimize end to end; the simulator was
  reproducible (identical `account_values.csv`) and the optimizer reproduced its objective for the same
  seed. Fixed a stale roads docs line (`9e4419d`).
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
- Completed Phase 5 (Operate and maintain): squash-merged pull request #51 as `5f6c704`, deleted the
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
