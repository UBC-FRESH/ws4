# Change Log

Newest entries last. Each milestone gets a dated entry that matches the roadmap status and the GitHub
issue comments.

## 2026-10-14

- Adopted the UBC-FRESH dev workflow in WS4: added `AGENTS.md`, `ROADMAP.md`, `CHANGE_LOG.md`, and the
  `notes/` tree. Phase 0 (Scope and design) is active on `feature/p0-scope-design`.
- P0.2: wrote the problem statement and scope in `notes/design/ws4-scope.md`.
- P0.3: recorded six architecture decisions in `notes/adr/0001` to `notes/adr/0006`.
- P0.4: wrote the architecture design in `notes/design/ws4-architecture.md`.
- P0.6: neutralized third-party naming in the skeleton. Renamed `ws4/io/patchworks_xml.py` to
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
