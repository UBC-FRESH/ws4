# Backlog

Living list of what is **not done**, so nothing is lost. Each item names its area, its status, and the
evidence or context. Update this in the same change set as the work it describes. The roadmap
(`ROADMAP.md`) and the GitHub issues are the plan of record; this note is the consolidated gap list.

Status values: `open`, `partial`, `blocked`, `done`.

## Matrix builder (P2.1)

- **Expression language.** `done` (bounded). Select statements evaluate with `ws4/io/expressions.py`:
  comparisons (`eq/ne/lt/le/gt/ge/in`), booleans (`and`/`or`/`not`), parentheses, and the functions
  `startswith`, `endswith`, `substring`, `int`, `Number`, `length`, and `if`. An expression the evaluator
  cannot parse falls back to the term matcher. Remaining: the wider function library (`curveId`,
  `lookupTable`, `attribute`, string and math functions). Evidence: the CT eligibility
  `not startswith(au,'t')` now evaluates correctly (MKRf PoC CT 586 vs reference 590).
- **Expression-sourced attribute curves.** `done`. An `<attribute>` with an `<expression>` (for example
  `curveId('Yield_'+au)`) is evaluated per stratum to a curve name and resolved against the recipe's
  curves. The evaluator now handles `curveId`, `attribute`, `lastindexof`, string concatenation, and
  arithmetic. The `<curve idref>` form and the `treatment eq 'X'` product context already match the k3z
  reference exactly.
- **`%f` / `%m` / `%au` label tokens and `factor` expressions.** `partial`. The `%f` (feature/product)
  and `%m` (managed/unmanaged) tokens expand per stratum, and an expression label such as
  ``'%f.area.%m.state.'+if(...)`` is evaluated after substitution. Open: the `%au` and species tokens,
  and the `factor` expression (which scales an attribute).
- **Account and feature/product de-duplication.** `partial`. Features and products now match the k3z
  reference exactly. Accounts are the union of feature and product labels, grouped by management state
  (`_MANAGED_`, `_UNMANAGED_`, `_ALL_`), and are close but not exact (k3z pct_light 1507 vs 1460).
- **Account zero-signal exclusion.** `open`. The reference excludes zero-signal families (the 47 extra
  labels in k3z are all `PL` / lodgepole pine). The exact rule is not yet reproduced; a naive
  "any curve value > 0" filter over-excludes.
- **Succession and `produce` semantics.** `partial`. `<transition>` is applied; `<succession>` and
  `<produce>` are parsed only as far as treatments need.
- **Intensive treatment lanes.** `done`. The k3z intensive variants (CT, PCT, F1-F3) now match the
  reference exactly (732/732/963/427 and 553/553/605/427). The fix was canonicalizing integral floats
  (`985502002.0` to `985502002`) so a numeric column matches an integer literal in a select.
- **Numeric vs literal matching.** `done`. State values are formatted canonically; an integral float is
  rendered without a decimal part.
- **Full MKRf canonical model.** `blocked`. Its generated `xml/forestmodel.xml` has no copies on the
  reachable annex remote; regenerate once the Windows machine's inputs are published. The canonical
  strata add `origin`, `statecode`, and `hasnatcurve` over the PoC's six themes (7048 tracks vs 2116).
- **Shapefile input.** `open`. The builder reads CSV/Parquet fragments; a shapefile needs the `geo`
  extra (`geopandas`/`pyogrio`). The reference fragments are shapefiles.
- **Expression-based input fields.** `open`. `<input block="Int(RES_KEY)" area="Shape_Area/10000"
  age="Int(AGE_2020)"/>` is used verbatim as a column name; the expressions are not evaluated.
- **Legacy matrix ingestion coverage.** `partial`. `ws4 ingest` maps the known legacy columns; other
  legacy layouts and the road model are not covered.

## Simulation (P2.2)

- **Operability and eligibility evaluation.** `done`. A scheduled treatment applies only where the
  fragment's track offers it (the Model II rule).
- **Succession and track switching during a run.** `done`. A treatment moves the fragment to its
  `new_track` and resets its offset.
- **Product yields.** `done`. Applying a treatment records the product yield (area times the product
  curve at the pre-treatment offset) to `product_values.csv`.
- **Route flows.** `open`. Products are not yet routed to destinations or costed.
- **Patch metrics over blocks.** `done`. `ws4/patch/metrics.py` groups the disturbed blocks into
  connected patches over the topology and reports the count, mean size, and size-class distribution;
  the simulator writes `patch_metrics.csv` when given a topology.
- **Deterministic replay test.** `done` (two runs are identical; an unoffered treatment is a no-op). A
  replay validated against a reference run remains open.

## Optimization and solver (P2.3-P2.6)

- **Objective and targets.** `done`. Weighted goal programming (`ws4/opt/objective.py`): per-year minimum
  and maximum with weights; targets load from YAML.
- **Operator registry and metaheuristics.** `partial`. `ws4/opt/operators.py` (toggle, shift, swap) and
  three solvers in `ws4/opt/solvers.py` — simulated annealing, tabu search, and iterated local search —
  selected by `OptimizeConfig.metaheuristic`, with multi-start (`OptimizeConfig.starts`). All seeded and
  reproducible. Open: ALNS and the wider operator set.
- **Solver core.** `partial`. The problem-adapter boundary is implemented (`ws4/opt/core.py`: a
  `Problem` with an evaluator, candidate moves, and an operator registry) and the solvers take it. Open:
  extracting a separate shared package for WS4/WS3/FHOPS.
- **Parallel and GPU execution substrate.** `partial`. Parallel multi-start runs across a process pool
  (`OptimizeConfig.workers`), one seeded start per worker, keeping the best. Open: the island model with
  elite sharing, NUMA-aware placement, and tensorized GPU move evaluation.
- **Math-heuristic layer (MIP).** `partial`. Destroy-repair large-neighbourhood search is an operator
  (`ws4/opt/operators.py`, `lns`); a warm start seeds the search from each block's first candidate
  (`OptimizeConfig.warm_start`); and `ws4/opt/mip.py` solves an option-selection MILP (HiGHS via
  `scipy.optimize.milp`) for a penalty **lower bound** and a candidate schedule. `OptimizeConfig.mip_bound`
  records the bound and the gap (`incumbent - bound`) in the run summary. Open: time-boxed MIP
  destroy-repair subproblems.
- **Telemetry and tuning.** `partial`. `ws4/opt/telemetry.py` writes a JSONL run header and a step
  record per iteration, and the optimizer writes `telemetry.jsonl`. Open: the tuners and the portfolio
  layer.

## Spatial, roads, accounts (P2.7-P2.8)

- **Block topology and patch metrics.** `partial`. The topology loader and patch metrics are done
  (`ws4/patch/metrics.py`). Open: core-area rules and edge contrast.
- **Road network, access, haul cost, exclusive routing.** `partial`. `ws4/roads/network.py` routes over
  the segment graph (shortest length and cost, nearest destination). The simulator routes each produced
  product to the block's single nearest destination (`route_values.csv`) — exclusive by construction,
  since each block is assigned to exactly one road node. Open: destination eligibility per product, and
  route cost accounts.
- **Account types and reports.** `partial`. `ws4/report.py` summarizes accounts, evaluates a ratio
  account, reports target status, and writes `report_accounts.csv` / `report_targets.csv`; `ws4 report`
  is a CLI command, and the optimizer writes a report at the end of a run. Open: duplicate and meta
  accounts, and chart output.
- **Unit conversion (map vs report units).** `open`.

## Programmatic model API (P2.9)

- **Model object and operations.** `done`. `ws4/model/api.py` holds one DataFrame per matrix table with
  `append` and `replace`.
- **Load from / write to the matrix; round-trip equality.** `done`. `Model.from_dataset` and
  `Model.write` round-trip a dataset (valid, same table lengths), and an empty model writes a valid
  dataset.

## Tooling and process

- **Shapefile/geo extra in CI.** `open`. The `geo` extra is declared but not installed in CI.
- **Broaden mypy coverage to `ws4/`.** `open`. Type checking currently covers `scripts/`, `tests/`, and
  `docs/conf.py` plus transitively imported modules.
- **Reference-matrix regression tests.** `partial`. The k3z pair is validated by hand; a committed
  fixture-based regression test is not in place.
- **Docs for each subsystem.** `partial`. The compiled dataset and ForestModelXML pages exist; the
  simulator, optimizer, spatial, and road subsystems are undocumented.
