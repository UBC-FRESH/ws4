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
- **Expression-sourced attribute curves.** `partial`. An `<attribute>` may source its curve from an
  `<expression>` (for example `curveId('Yield_'+au)`). The parser records the expression; the builder
  skips it, so those features/products are missing. The `<curve idref>` form and the
  `treatment eq 'X'` product context now match the k3z reference exactly (features and products). Open:
  the `<expression>`-sourced curves (the MKRf model).
- **`%f` / `%m` / `%au` label tokens and `factor` expressions.** `open`. Attribute labels and factors
  use substitution tokens and expressions. The builder uses the raw label.
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

- **Objective and targets.** `open`. Weighted goal programming is not implemented.
- **Operator registry and metaheuristics.** `open`. SA, Tabu, ILS are not implemented.
- **Solver core.** `open`. The shared package boundary is a recommendation, not code.
- **Parallel and GPU execution substrate.** `open`.
- **Math-heuristic layer (MIP).** `open`.
- **Telemetry and tuning.** `open`.

## Spatial, roads, accounts (P2.7-P2.8)

- **Block topology and patch metrics.** `open`. `ws4/patch/topology.py` is a loader only.
- **Road network, access, haul cost, exclusive routing.** `open`. `ws4/roads/network.py` is a loader only.
- **Account types and reports.** `open`.
- **Unit conversion (map vs report units).** `open`.

## Programmatic model API (P2.9)

- **Model object and operations.** `open`.
- **Load from / write to the matrix; round-trip equality.** `open`.

## Tooling and process

- **Shapefile/geo extra in CI.** `open`. The `geo` extra is declared but not installed in CI.
- **Broaden mypy coverage to `ws4/`.** `open`. Type checking currently covers `scripts/`, `tests/`, and
  `docs/conf.py` plus transitively imported modules.
- **Reference-matrix regression tests.** `partial`. The k3z pair is validated by hand; a committed
  fixture-based regression test is not in place.
- **Docs for each subsystem.** `partial`. The compiled dataset and ForestModelXML pages exist; the
  simulator, optimizer, spatial, and road subsystems are undocumented.
