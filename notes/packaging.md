# Packaging and docs from a clean checkout (P3.6)

A clean checkout installs into a fresh virtual environment, runs end to end from the command line,
and builds its documentation with warnings as errors.

## Install

```bash
python -m venv /tmp/ws4-venv
/tmp/ws4-venv/bin/python -m pip install --upgrade pip
/tmp/ws4-venv/bin/python -m pip install .
/tmp/ws4-venv/bin/python -c "import importlib.metadata as m; print(m.version('ws4'))"
```

Result: `ws4 0.0.1` installs, and `ws4 --help` lists the commands.

## Command line end to end

```bash
ws4 build --xml examples/synthetic/recipe.xml --fragments examples/synthetic/fragments.csv --out compiled
ws4 simulate --dataset compiled --schedule schedule.csv --years 5 --out run
ws4 report --run run
ws4 validate --dataset compiled
```

Result: `Built dataset`, `Simulation complete`, `Report written`, and `Dataset is valid`. The run
directory holds `account_values.csv`, `product_values.csv`, `dataset.json`, `report_accounts.csv`,
and `report_targets.csv`.

## Docs

```bash
python -m pip install -r docs/requirements.txt
python -m sphinx -b html docs _build/html -W -q
```

Result: the docs build with warnings as errors (exit status 0). The published site at
`https://ubc-fresh.github.io/ws4/` returns HTTP 200.

## Notes

- The core install (no extras) covers build, simulate, report, validate, and ingest. The `geo` extra
  adds the shapefile reader, and the `opt` extra adds `scipy` for the mixed-integer bound.
- The command-line options for the spatial constraints are `--topology`, `--max-opening-ha`,
  `--min-green-up-years`, and `--spatial-override` (P3.8).
