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
  matrix builder, and added legacy matrix ingestion. The parser handles the real MKRf recipe
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
  MKRf PoC CT eligibility now evaluates (`not startswith(au,'t')`).
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
  evaluates an attribute's expression per stratum to a curve name. On the MKRf PoC the expression-sourced
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
