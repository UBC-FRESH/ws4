# P114: Scenario price paths

## Outcome

WS4 now reads a typed, read-only `prices.v1` table and writes a base-relative
comparison with provenance. The table carries `base`, `high`, `low`, and
`policy_shock` paths; each row names its product, period, value, unit, currency,
region, source, and source version. Every table must state that its values are
`not a forecast`, and the loader rejects a table that does not.

The command is:

```bash
ws4 price-paths --table tests/fixtures/prices/paths.json --out runtime/prices
```

It writes `price_path_comparison.csv`, `price_path_report.md`, and
`price_path_provenance.json`. The comparison reports `base_value`, `delta`, and
`delta_pct` for each path/product/period. The percent delta is null when the base
value is zero. The sidecar records the input file's name, byte size, and SHA-256,
the path and product/period grid, each path's source and source version, the
comparison definition, and each output file's size and digest. The sidecar records
every distinct path/source/source-version combination with the products and periods
it covers, so a path that draws on more than one source keeps all of its attribution.

## Validation

The loader rejects:

- a missing base path or an unknown path;
- a duplicate path/product/period row;
- a path that does not cover exactly the base product/period grid;
- a product with mixed units, or a table with mixed currencies or regions;
- a negative or non-finite value, or a negative or non-integer period;
- a missing `not_a_forecast` field or a statement that omits `not a forecast`.

The fixture at `tests/fixtures/prices/paths.json` is synthetic and carries that
label. It has two products, three periods, and all four named paths.

## Verification

- `python -m pytest tests/test_prices.py tests/test_cli.py -q` — 50 passed.
- `python scripts/dashboard.py` — `OVERALL: GREEN` on all seven gates (lint,
  format, types, tests, validator, docs, docstrings).
- `python scripts/check_workflow.py` — `0 error(s), 0 warning(s)`.
- Manual run of the fixture command produced the three artifacts; the report
  repeated the caveat and the sidecar's recorded digests matched the files.

An automated review found that the provenance sidecar recorded only the
first row's source for each path. The loader already accepted per-row sources, so the
sidecar now records every distinct path/source/source-version combination with the
products and periods it covers, and a focused test holds that behaviour.

## Scope boundary

The change does not touch the compiled dataset, growth, the simulator, the
objective, constraints, the schedule, or the solver. There is no price forecast,
currency conversion, inflation adjustment, or missing-value inference. The table
is the shared boundary that a scenario or an external client can populate; this
repository only consumes it.

## Limits

- A digest detects change; it is not a signature or a trust anchor.
- The report does not rank the paths or claim that one is more likely.
- The fixture's values are synthetic test data, not a market source.
- A table may carry a subset of the non-base paths, but every present path must
  cover the base grid exactly.

## Artifacts

- `ws4/prices.py`
- `ws4/cli.py`
- `tests/test_prices.py`
- `tests/fixtures/prices/paths.json`
- `tests/test_cli.py`
- `docs/reference/prices.rst`
- `docs/reference/index.rst`, `docs/llms.txt`
- `ROADMAP.md`, `CHANGE_LOG.md`

## Pull request

To be opened against `main` with `Part of #749`; merge waits for maintainer
approval.
