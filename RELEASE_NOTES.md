# WS4 0.1.0

Released: 2026-10-15

WS4 is a CLI-first, HPC-ready forest estate model that treats space as first-class: fragments are the
decision units, blocks aggregate them at runtime, and adjacency, patch structure, and road access
participate in simulation and optimization.

This is the first release. It delivers a working model and a working optimization stack, verified end
to end.

## Install

```bash
pip install .            # core: build, simulate, optimize, report, validate, ingest
pip install ".[geo]"     # add the shapefile fragment reader
pip install ".[opt]"     # add scipy for the mixed-integer bound
```

Requires Python 3.11 or newer, on Linux.

## Quick start

```bash
ws4 build    --xml examples/synthetic/recipe.xml --fragments examples/synthetic/fragments.csv --out compiled
ws4 simulate --dataset compiled --schedule schedule.csv --years 30 --out run
ws4 report   --run run
ws4 validate --dataset compiled
```

## What is included

- **Ingestion and compilation.** A ForestModelXML recipe and a fragment inventory compile into a
  versioned, columnar matrix dataset with a manifest. Legacy matrix datasets ingest directly. The
  builder matches the reference compiled matrices on all nine core variants, across tracks, strata,
  treatments, blocks, features, products, and `protoaccounts`, and it reproduces the full MKRF canonical
  model exactly (tracks, strata, treatments, blocks, features, products, and `protoaccounts`).
- **Simulation.** An annual engine with growth, succession, treatments, block-level operability,
  product yields, patch metrics, and product routing to the nearest destination. The simulator is
  deterministic given a schedule and the dataset.
- **Optimization.** Weighted goal programming with a layered, pluggable search stack: operators
  (toggle, shift, swap, large-neighbourhood search), simulated annealing, tabu search, iterated local
  search, multi-start (serial and process-pool parallel), warm starts, and a mixed-integer penalty
  bound with gap tracking. Every search records its seed and reproduces its result.
- **Spatial constraints.** A maximum opening size and a green-up interval are reported per year and
  enforced in the optimizer's objective, with an explicit override.
- **Accounts and reporting.** Summary and ratio accounts, target status, and a report writer.
- **Programmatic model API.** Build or patch the model in memory, and round-trip it with the file path.
- **Reproducibility.** Recorded seeds, a deterministic simulator, validated datasets, and a run
  directory that records the dataset manifest.

## Performance

- The matrix builder compiles 100 000 fragments in about 1.7 s.
- The C5 sample (16 174 fragments, 130 423 curves) simulates 30 years in about 4.2 s.

See `notes/performance.md`.

## Verification

- `python -m pytest`: 278 tests pass, with a 90 percent branch-coverage gate (94.28 percent).
- `python scripts/dashboard.py`: lint, format, strict types, tests, the workflow validator, and the
  docs build, all green.
- The acceptance checks (`scripts/acceptance.py`), the C5 end-to-end test, and a clean-checkout
  install, command-line run, and docs build all pass. See `notes/reports/p3-verify.md`.

## Known gaps

The first release is complete against its scope. These items are recorded in `notes/backlog.md` with a
target phase:

- **Blocked:** nothing release-blocking. The MKRF canonical model now reproduces exactly; only the
  producer's git-annex location log for its four large artifacts is not on `origin`, so a fresh clone
  cannot `get` them (a local `reinject` workaround was used). The objects themselves are on
  `arbutus-s3`.
- **Future work:** the wider expression library; succession and `produce` semantics; wider
  legacy-ingestion coverage; a reference replay; the wider operator set and ALNS; a shared solver-core
  package; the island model and tensorized GPU moves; time-boxed MIP subproblems; the tuners and the
  meta-meta-heuristic portfolio; core-area rules and edge contrast; destination eligibility and route
  cost accounts; duplicate and meta accounts and chart output; and unit conversion.
- **Out of scope:** a graphical interface, carbon accounting, supply-chain modules, exact spatial
  optimization, vendor-specific runtime artifacts, and a hosted service.

## Documentation

Published at https://ubc-fresh.github.io/ws4/.

## License

Apache-2.0. See `LICENSE`.
