# WS4 0.2.0

Target release: 2026-10-26

WS4 0.2.0 turns the 0.1.0 core into a production-facing analyst system: the model still treats
space as first-class, but the search, map, provenance, target, and provider surfaces are now
designed for review rather than one-off runs.

## Install

```bash
pip install ws4==0.2.0   # published release
pip install .            # core: build, simulate, optimize, report, validate, ingest
pip install ".[geo]"     # add the shapefile fragment reader
pip install ".[lidar]"   # add FEMIC LidarBC mapping dependencies
pip install ".[carbon]"  # add the optional libcbm carbon engine
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
- **Native FEMIC LiDAR products (P52).** Register and validate versioned LidarBC bundles; map
  native-resolution slope/CHM and optional VRI/tree evidence to fragments and blocks; and
  integrate optional `lidar_*` fields with bundle and checksum provenance. The simulator loads the
  expanded dataset unchanged; no WS4 model semantics consume the fields yet.
- **Forest carbon accounting (P58).** FEMIC carbon packages, libcbm SIT compilation, the
  `ws4 carbon` command, carbon accounts and reports, a block-level ledger, and carbon-aware
  optimizer targets. TSA24/MKRF bounded validation and byte-identical replay are recorded.
- **Hydrology response screening (P57).** Pinned FEMIC hydrology bundles, explicit reviewed
  crosswalks, schedule-level flood-risk screening, and optional `flood.*` accounts in the
  optimizer. This is screening-only; no hydrologist review or operational flood claim is made.
- **Disturbance events (P56).** A read-only `femic.disturbance.v1` consumer and
  `ws4 disturbance` report for event year/type/severity and affected blocks. No compiled-dataset,
  simulator, or optimizer behavior changed.
- **Route-event cache (P46).** A per-block route-event cache and exact ledger replay for
  build and maintenance. The c5 warm cache was 8.25x faster than the full path with parity
  within `1.9e-8`; delivery and `initial_roads: existing` configurations keep the full path.

## Verification

- P53 head: clean-checkout build and test, dashboard, sdist/wheel build, `twine check`, isolated
  installs, entry points, synthetic build/validate/simulate/report smoke, and Pages checks pass.
- P52 LiDAR: 61 tests; real TFL 6 bundle map/integrate/simulator load; WS4/FEMIC parity
  `7.1e-15` and WS4/FHOPS parity `0.0`.
- P56 disturbance: 13 unit tests and 4 CLI tests; read-only behavior verified.
- P57 hydrology: 39 contract tests, dashboard green, screening and flood-account pricing tests;
  public crosswalk and hydrologist review remain open as noted below.
- P58 carbon: WS3/WS4 TSA24 parity `max_abs = 0.0`; bounded TSA24/MKRF carbon-aware runs were
  exact-verified; accounts, pools, flux, and manifests replay byte-identically.
- P46 route events: c5 parity `1.9e-8`; warm cache 0.037 s versus 0.303 s full path.
- The P55 final 0.2.0 candidate re-runs these gates on the final head. No tag is created without
  explicit approval.

See `notes/reports/p53-release-candidate.md` for the 0.2.0 candidate evidence and the P52, P57,
and P58 close-out reports for the phase evidence.

## Known gaps

- Environmental accounts (P54) are planned for a later phase and are **not** in 0.2.0.
- Route evaluation: P45 profiling/design and the P46 route-event cache are included; no
  incremental route evaluator landed. Delivery and opened-road configurations still take the full
  path.
- Carbon: the full TSA24 landscape carbon-aware search is not complete; the TSA24 block ledger
  differs from the exact engine by about 0.03% after disturbances; the same-landscape GCBM
  comparison awaits the FEMIC walltowall export (P115.4); species-resolved curves/crosswalk review
  and CBM4 remain deferred.
- Hydrology: there is no reviewed public crosswalk, hydrologist review, or independent WS4
  tail-check validation; flood accounts are optimizer-only and whole-schedule; no FHOPS hydrology
  integration exists.
- Disturbance events are report-only; no simulator or optimizer semantics consume them.
- LiDAR fields are persisted dataset evidence; no WS4 operability or optimization constraints
  consume them yet.
- Volume/DBH validation is documented but data-limited; the managed/young ground-plot test in
  ADR 0003 remains blocked on management-origin data.
- Deterministic seeds, bounded searches, and heuristic schedules are not certified optimal.
- The AAC is a policy ceiling, not an operational or ecological guarantee.

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
