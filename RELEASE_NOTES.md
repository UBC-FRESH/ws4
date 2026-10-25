# WS4 0.2.0

Target release: 2026-10-25

WS4 0.2.0 turns the 0.1.0 core into a production-facing analyst system: the model still treats
space as first-class, but the search, map, provenance, target, and provider surfaces are now
designed for review rather than one-off runs.

## Install

```bash
pip install .            # core: build, simulate, optimize, report, validate, ingest
pip install ".[geo]"     # add the shapefile fragment reader
pip install ".[opt]"     # add the optimization extras
pip install ".[web]"     # add the web UI and map serving extras
```

Requires Python 3.11 or newer, on Linux.

## What is new since 0.1.0

- **Search and decision review.** Portfolio and multi-objective search, the MIP bound lane,
  constraint repair, flow and inventory ceilings, normalized goal priorities, live run surfaces,
  and a comparison map over MVT tiles.
- **Artifact depth.** Search members, schedules, targets, fronts, portfolio reports, LP
  sensitivity, failure metadata, console links, and safe artifact downloads are inspectable from
  the Search tab. Durable compare tiles and pre-warm support make the A/B map usable at scale.
- **Target operations.** Multi-account target creation, browser-side validation, and a pre-save
  `targets.yaml.bak` backup.
- **Map and account surfaces.** Map operations, account browsing and activation, model-derived
  spatial layers, production map serving, and viewport controls.
- **Provenance and limitations.** Dataset-quality sidecars, GBR instance provenance, model
  boundary ADRs, stratified ground-plot validation, runtime-provenance reports, and explicit
  no-optimality/no-AAC-guarantee language.
- **Workflow execution.** The FreshForge instance providers, bounded smoke runs, a provenance
  gate, and CI provider smoke on a tiny fixture.
- **Reference instances.** Great Bear Rainforest North (TSA 46) and South (TSA 47) remain
  standalone instances with published docs and provenance.

## Verification

- Clean-checkout build and test: pass.
- `python scripts/dashboard.py`: lint, format, strict types, tests, workflow validator, docs, and
  docstrings all green.
- sdist and wheel build; `twine check` pass; isolated installs and entry points pass.
- Synthetic build → validate → simulate → report smoke passes.
- The ws4 docs, limitations, API, and both GBR instance sites return 200.

See `notes/reports/p53-release-candidate.md` for the 0.2.0 evidence.

## Known gaps

- Route-evaluation performance (P45) profiling and design are included; no incremental route code
  landed. Forest-carbon accounting (P51) and native LiDAR products (P52) remain later phases and
  are **not** in 0.2.0.
- Volume/DBH validation is documented but data-limited; the managed/young ground-plot test in
  ADR 0003 remains blocked on management-origin data.
- Deterministic seeds, bounded searches, and heuristic schedules are not certified optimal.
- The AAC is a policy ceiling, not an operational or ecological guarantee.
- PyPI publishing remains out of scope.

## Documentation

Published at https://ubc-fresh.github.io/ws4/.

## License

Apache-2.0. See `LICENSE`.

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
- **Performance on space-and-roads models.** The simulator, route model, patch accounts, edge contrast,
  and core-area rules run inside the optimizer's objective, so a full C5-class evaluation is slow
  (minutes, not milliseconds). This is the next major effort after this release; the plan is
  `notes/design/ws4-performance.md`.
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
