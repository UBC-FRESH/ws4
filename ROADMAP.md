
# WS4 Roadmap

This roadmap is the plan of record and the issue tracker map for WS4. Keep it in step with the GitHub
issues, `CHANGE_LOG.md`, and `notes/`. `scripts/check_workflow.py` parses the phase headers, status
lines, and checkboxes below, so keep their format.

Every phase starts as `planned` with `Parent issue: TBD`. Activate a phase only after its parent issue
exists and the maintainer approves it.

## Issue Tracker Map

| Phase | Parent issue | Branch | Status |
| --- | --- | --- | --- |
| P0 Scope and design | #1 | `feature/p0-scope-design` | complete |
| P1 Contracts and prototype | #10 | `feature/p1-contracts-prototype` | complete |
| P2 Build | #15 | `feature/p2-build` | complete |
| P3 Verify | #26 | `feature/p3-verify` | complete |
| P4 Release and deploy | #36 | `feature/p4-release` | complete |
| P5 Operate and maintain | #44 | `feature/p5-operate` | complete |
| P6 Performance and scalability | #60 | `feature/p6-performance` | complete |
| P7 Parity and the analyst workflow | #82 | `feature/p7-parity` | complete |
| P8 Verify the replacement claim | #90 | `feature/p8-verify` | complete |
| P9 Spatial performance and memory | #97 | `feature/p9-memory` | complete |
| P11 The derived targets and the sample's own files | #112 | `feature/p11-derived-targets` | complete |
| P12 Spatial decision match | #120 | `feature/p12-spatial-decisions` | complete |
| P13 The reference's remaining readings | #128 | `feature/p13-reference-readings` | complete |
| P14 Optimizer search for aggregate targets | #133 | `feature/p14-optimizer-seeding` | complete |
| P15 A spread-connectivity account | #138 | `feature/p15-spread-connectivity` | complete |
| P16 The bridge at the same footprint | #141 | `feature/p16-bridge-matched` | complete |
| P17 Roads opened to the period | #145 | `feature/p17-opened-roads` | complete |
| P18 A graphical web front end | #146 | `feature/p18-web-frontend` | complete |
| P19 Model-derived spatial layers and map scale | #161 | `feature/p19-spatial-layers` | complete |
| P20 Production map serving | #183 | `feature/p20-map-lod` | complete |
| P21 Search quality and validation | #190 | `feature/p21-search-quality` | complete |
| P22 Map operations | #198 | `feature/p22-map-ops` | complete |
| P23 Accounts and target activation | #206 | `feature/p23-target-browser` | complete |
| P24 Search portfolio and multi-objective | #207 | `feature/p24-search-portfolio` | complete |
| P25 Constraint repair and flow ceilings | #214 | `feature/p25-constraints` | complete |
| P26 Reproducibility and data quality | #219 | `feature/p26-repro-quality` | complete |
| P27 Goal normalization and priority tiers | #227 | `feature/p27-normalization` | complete |
| P28 Inventory and flow ceilings | #233 | `feature/p28-inventory` | complete |
| P29 MIP lane and exact small-instance validation | #238 | `feature/p29-mip` | complete |
| P30 Live run surfaces | #242 | `feature/p30-live-surfaces` | complete |
| P31 Comparison map over MVT | #257 | `feature/p31-compare-map` | complete |
| P32 Dataset provenance and limitations | #249 | `feature/p32-provenance` | complete |
| P35 Instance provenance adoption | #267 | `feature/p35-provenance` | complete |
| P36 Workflow conformance | #273 | `feature/p36-conformance` | complete |
| P37 FreshForge provenance gate | #278 | `feature/p37-provenance-gate` | complete |
| P33 Search artifact browser | #261 | `feature/p33-search-ui` | complete |
| P34 Search launcher | #265 | `feature/p34-search-launch` | complete |
| P38 Instance FreshForge provider execution | #287 | `feature/p38-provider` | complete |
| P40 Bounded provider workflow execution | #297 | `feature/p40-smoke` | complete |
| P41 Provider smoke in CI | #303 | `feature/p41-ci-smoke` | complete |
| P47 Model boundary record | #311 | `feature/p47-boundary` | complete |
| P48 Ground-plot volume and DBH validation | #324 | `feature/p48-ground-plots` | complete |
| P49 Managed/young validation pre-registration | #335 | `feature/p49-preregistration` | complete |
| P50 Runtime provenance and release verification | #345 | `feature/p50-runtime-provenance` | complete |
| P51 Release-candidate verification | #351 | `feature/p51-release-candidate` | complete |
| P53 Version 0.2.0 release preparation | #371 | `feature/p53-v020` | complete |
| P55 Final 0.2.0 release candidate | #388 | `feature/p55-final-rc` | complete |
| P56 Disturbance event consumer | #393 | `feature/p56-disturbance-consumer` | complete |
| P58 Forest carbon accounting and carbon-aware planning | #357 | `feature/p58-carbon` | complete |
| P59 LiDAR in the web UI | #417 | `feature/p59-lidar-ui` | complete |
| P60 Harden hydrology use with validation evidence | #415 | `feature/p60-closeout` | complete |
| P61 Carbon and libcbm in the web UI | #430 | `feature/p61-carbon-ui` | complete |
| P62 Harden the hydrology consumer and explicit road/culvert exposure | #437 | `feature/p62-hydrology-consumer` | active |
| P39 Account browser polish | #293 | `feature/p39-account-polish` | complete |
| P42 Target operations | #308 | `feature/p42-target-ops` | complete |
| P43 Search artifact depth | #330 | `feature/p43-search-depth` | complete |
| P44 Comparison and map operations | #341 | `feature/p44-compare-ops` | complete |
| P45 Route evaluation performance | #368 | `feature/p45-route-profile` | complete |
| P52 Consume FEMIC-compiled LidarBC products | #317 | `feature/p52-lidar-products` | complete |
| P57 Consume FEMIC hydrology response bundles | #395 | `feature/p57-hydrology-response` | complete |
| P46 Cached route event ledger | #382 | `feature/p46-route-events` | complete |
| P10 Documentation and the API-first workflow | #104 | `feature/p10-docs-api` | complete |

## Lifecycle Map

| Stage | Phases | Exit criteria |
| --- | --- | --- |
| Scope and design | P0 | Goal, scope, and out-of-scope items recorded; architecture decisions in ADRs |
| Contracts and prototype | P1 | Data contracts defined; smallest end-to-end prototype exercises them |
| Build | P2 | Agreed scope implemented, one task at a time, with tests and docs |
| Verify | P3 | Acceptance checks pass; evidence recorded in the changelog |
| Release and deploy | P4 | Tagged release; published docs verified from a clean checkout |
| Operate and maintain | P5 | Review cadence held; incoming ideas triaged |

## Conventions

- A phase is `P<n>`. A task is `P<n>.<m>`. A subtask is a checklist item inside the task's issue body. Three levels at most.
- Status values are `planned`, `active`, `pr-open`, `complete`, and `deferred`.
- A phase becomes `complete` only after its pull request merges to `main` and its parent issue closes.

## Phase 0: Scope and design

Parent issue: #1
Branch: `feature/p0-scope-design`
Status: complete

Goal: give WS4 a workflow contract, a recorded scope, and a reviewed architecture. The repository
already carries a code skeleton; this phase turns it into a governed project with a plan of record and
decisions that later phases can build on.

- [x] P0.1 Adopt the workflow contract and governance files (#2)
  - [x] `AGENTS.md`, `ROADMAP.md`, `CHANGE_LOG.md`, and `notes/` index
- [x] P0.2 Write the problem statement and scope (#3)
  - [x] `notes/design/ws4-scope.md`
- [x] P0.3 Record the architecture decisions as ADRs (#4)
  - [x] `notes/adr/0001` to `notes/adr/0006`
- [x] P0.4 Write the architecture design (#5)
  - [x] `notes/design/ws4-architecture.md`
- [x] P0.5 Install the workflow tooling (#6)
  - [x] Copy the validator, dashboard, docs skeleton, tests, and CI from the seed
  - [x] Make `python scripts/dashboard.py` green on this repository
- [x] P0.6 Neutralize third-party naming in the skeleton (#7)
  - [x] Rename the XML importer and reword the CLI help, README, and docstrings
- [x] P0.7 Record the optimization and execution architecture (#9)
  - [x] Layered optimization stack, generalized from the lab's metaheuristic toolkit
  - [x] Parallel and GPU execution substrate; Python-first with C++ kernels behind an API
  - [x] Telemetry-driven tuning and the meta-meta-heuristic portfolio

Acceptance criteria:

- The scope states the problem, users, in-scope and out-of-scope items, and success criteria.
- Each architecture decision is an ADR with context, decision, consequences, and alternatives.
- The architecture note covers the data model, compilation, simulation, optimization, spatial and road
  subsystems, accounts, CLI, and performance, and it names its open questions.

Phase 0 verification:

- `python -m pytest` (smoke test)
- `python scripts/dashboard.py` (after P0.5)

## Phase 1: Contracts and prototype

Parent issue: #10
Branch: `feature/p1-contracts-prototype`
Status: complete

Goal: fix the data contracts and build the smallest end-to-end prototype that exercises them on
synthetic data.

- [x] P1.1 Define the compiled-dataset schema and manifest in `docs/` (#11)
  - [x] `docs/reference/compiled-dataset.rst`, `ws4/model/schema.py`, and `ws4 validate`
  - [x] `tests/test_schema.py` with a failing case per invariant
- [x] P1.2 Build a prototype that compiles, simulates, and reports on a tiny synthetic landscape (#12)
  - [x] Synthetic fixture in `examples/synthetic/`
  - [x] Minimal `ws4 build` and `ws4 simulate`; `tests/test_prototype.py`
- [x] P1.3 Adopt the ForestModelXML format and record the construction paths (#13)
  - [x] `notes/design/ws4-matrix-builder-and-interop.md` and ADRs 0011 and 0012
  - [x] Update the scope and the architecture note

## Phase 2: Build

Parent issue: #15
Branch: `feature/p2-build`
Status: complete

Goal: implement the agreed scope, one task at a time, on the phase branch.

- [x] P2.1 Implement the ForestModelXML matrix builder and legacy dataset ingestion (#16)
  - [x] ForestModelXML parser and structural validation (parses the real MKRF recipe: 1057 curves, 11 selects, 2 treatments)
  - [x] Matrix builder for the non-expression subset; legacy matrix ingestion with a recorded mapping
  - [x] The Model II expansion engine: enumerate the reachable strata, expand each into a track, connect treatments to target strata (`ws4/build/expansion.py`)
  - [x] Block splitting into portions, per-track treatment expansion, and retention splits
  - [x] Matches reference compiled matrices exactly on tracks, strata, treatments, blocks, features, products, and `protoaccounts` (nine core variants)
  - [x] Full expression language, expression-sourced curves, shapefile input, and expression-based `<input>` fields
  - [x] Emit `protoaccounts` and preserve a curated `accounts` table
- [x] P2.2 Implement the simulation engine (#17)
  - [x] Operability (track-offered treatments), track switching, feature accounts, deterministic replay
  - [x] Product yields; vectorized curve evaluation; a full run on the C5 sample
  - [x] Patch metrics and product routing to the nearest mill
- [x] P2.3 Implement the optimization engine: objective, operators, and one metaheuristic (#18)
  - [x] Weighted-goal objective and YAML targets
  - [x] Operator registry (toggle, shift, swap, LNS)
  - [x] Simulated annealing, tabu search, and iterated local search; multi-start
- [x] P2.4 Implement the solver core: the shared operator/metaheuristic/tuning/telemetry package (#19)
- [x] P2.5 Implement the parallel and GPU execution substrate (#20)
  - [x] Process-pool parallel multi-start and warm starts
- [x] P2.6 Implement the math-heuristic layer (MIP bounds, warm starts, destroy-repair) (#21)
- [x] P2.7 Implement the spatial and road subsystems (#22)
  - [x] Patch metrics over the block topology
  - [x] Road network routing (length, cost, nearest destination) and simulator product flows
- [x] P2.8 Implement accounts and reporting (#23)
  - [x] Account summary, ratio account, target status, and a report writer; `ws4 report`
- [x] P2.9 Implement the programmatic model API (build or patch the model in memory) (#24)
  - [x] `ws4/model/api.py` with append/replace and a dataset round-trip

Deferred from P2, triaged in `notes/backlog.md` (none is release-blocking):

- post-release (a future build phase): the wider operator set beyond LNS; the shared solver-core
  package; islands and tensorized GPU moves; time-boxed MIP subproblems; the tuners and the portfolio
  layer; core-area rules and edge contrast; destination eligibility and route cost accounts; duplicate
  and meta accounts and chart output; succession and `produce` semantics; the wider expression library;
  and unit conversion.
- blocked: the full MKRF canonical model (needs its generated XML).

## Phase 3: Verify

Parent issue: #26
Branch: `feature/p3-verify`
Status: complete

Goal: show that the build meets its acceptance criteria, with evidence, and surface every gap before
release.

- [x] P3.1 Run the acceptance checks and record the evidence (#27)
  - [x] Matrix builder: rebuild each core variant and compare tracks, strata, treatments, blocks,
        features, products, and `protoaccounts` to the reference
  - [x] Simulator: reproduce the prototype's account values, and run the C5 end-to-end functional test
  - [x] Optimizer: satisfy a target set within a stated tolerance, and replay the schedule
  - [x] Spatial and road: route products and record patch metrics
  - [x] Programmatic API and the file path produce the same model
  - [x] Record the evidence, and any failure with its cause and backlog entry, in `CHANGE_LOG.md`
- [x] P3.2 Verify determinism and reproducibility (#28)
  - [x] The simulator is deterministic: the same schedule produces identical account values across runs
  - [x] Every stochastic search records its seed, and the same seed reproduces the same result
  - [x] A parallel multi-start run matches the serial run for the same seeds
  - [x] A warm start is deterministic: the same seed reproduces the same result
  - [x] A run directory is self-describing: it records the config, the seed, and the dataset manifest
- [x] P3.3 Verify correctness: reference regression and invariants (#29)
  - [x] Commit a fixture-based regression test for the matrix builder against a reference matrix
  - [x] Property tests for the Model II expansion invariants (every stratum has a track; every treatment
        connects to a real target; retention splits conserve area)
  - [x] The schema invariants hold on every compiled dataset
  - [x] The optimizer's MIP bound is a valid lower bound on the penalty
- [x] P3.4 Verify the spatial constraints (#30)
  - [x] Adjacency and topology are visible in the outputs: patch count, mean size, and the largest
        opening per year
  - [x] Adjacency, maximum opening size, and green-up are enforced, and violated only by an explicit
        override (implemented in P3.8)
  - [x] Patch metrics match an independent calculation on a small topology
- [x] P3.5 Verify scale and performance (#31)
  - [x] Record the C5 sample's ingest, simulate, optimize, and route runtimes
  - [x] Build and run a larger synthetic landscape; record the runtime and the peak memory
  - [x] Confirm the simulator's curve evaluation is vectorized per curve, not per fragment
  - [x] Profile the hot paths and record the block-aggregation cost
- [x] P3.6 Verify packaging and docs from a clean checkout (#32)
  - [x] Install the package into a fresh virtual environment from the checkout
  - [x] Run the command line end to end on the synthetic fixture
  - [x] Build the docs with warnings as errors, and confirm the published site is reachable
- [x] P3.7 Triage the deferred items and write the verification report (#33)
  - [x] Confirm every deferred item in `notes/backlog.md` has a reason and a target phase
  - [x] Confirm the roadmap's deferred list and `notes/backlog.md` agree
  - [x] Write the verification report with the evidence and the release recommendation
- [x] P3.8 Implement and enforce the spatial constraints (#34)
  - [x] `ws4/patch/constraints.py`: the largest opening per year, opening violations, green-up
        violations, and a combined penalty
  - [x] The simulator reports per-year violations in `spatial_violations.csv`
  - [x] The optimizer penalizes violations, with an explicit `allow_spatial_override`
  - [x] Tests for the functions, the simulator report, and the optimizer (enforced and override)

## Phase 4: Release and deploy

Parent issue: #36
Branch: `feature/p4-release`
Status: complete

P4 is complete: pull request #43 squash-merged as `d8ecd72`, the branch deleted, the annotated tag
`v0.1.0` created and pushed, the GitHub release `v0.1.0` published with the sdist and the wheel, the
docs site verified, and the published artifact verified from a fresh install (P4.6). Close-out report:
`notes/reports/p4-closeout.md`.

Goal: tag a release, publish the artifacts and the docs, and verify the published release from a clean
checkout.

- [x] P4.1 Prepare the release: version, changelog, license, citation, and packaging metadata (#37)
  - [x] Set the version in `pyproject.toml` and `ws4/__init__.py`
  - [x] Confirm the license, citation, and package metadata
  - [x] Confirm `CHANGE_LOG.md` is current through P3
- [x] P4.2 Write the release notes and the known-gaps list (#38)
  - [x] Write the release notes for the first release
  - [x] State the known gaps (the blocked MKRF model, and the future work in `notes/backlog.md`)
- [x] P4.3 Build and verify the release artifacts (sdist and wheel) from a clean checkout (#39)
  - [x] Build the sdist and the wheel
  - [x] Install the wheel into a fresh virtual environment and run the command line end to end
  - [x] Confirm the artifacts contain the package and not the tests or the notes (added `MANIFEST.in`)
- [x] P4.4 Publish the documentation site and verify it from a clean checkout (#40)
  - [x] Confirm the `Docs` workflow builds and deploys from `main` (run `38785009892`)
  - [x] Verify the published site is reachable and matches the checkout
  - [x] Add the subsystem pages assigned to P4 (simulator, optimizer, spatial, roads)
- [x] P4.5 Tag the release and publish the artifacts (#41, maintainer approval required)
  - [x] Create the annotated tag (`v0.1.0` at `d8ecd72`)
  - [x] Publish the artifacts after approval, and record the locations and commands (the GitHub release
    `v0.1.0`; see `notes/reports/p4-closeout.md`)
- [x] P4.6 Verify the published release (#42)
  - [x] Install the published artifact into a fresh virtual environment
  - [x] Run the acceptance checks against the installed package
  - [x] Confirm reproducibility: the same configuration and seed reproduce a run

## Phase 5: Operate and maintain

Parent issue: #44
Branch: `feature/p5-operate`
Status: complete

P5 is complete: pull request #51 squash-merged as `a8cb148`, the branch deleted, and parent issue #44
closed. Delivered the review cadence, issue triage, dependency and security maintenance (Dependabot
version updates and security updates enabled), the roadmap/backlog/changelog sync checklist, the
release and patch policy, and the maintainer and handover guide. Close-out report:
`notes/reports/p5-closeout.md`.

Goal: keep the project current: triage incoming ideas, review on a cadence, and close out cleanly.

- [x] P5.1 Set a review cadence and record the first review (#45)
- [x] P5.2 Stand up issue triage: labels, templates, and a triage cadence (#46)
- [x] P5.3 Dependency and security maintenance: automated updates and a review cadence (#47)
- [x] P5.4 Keep the roadmap, backlog, and changelog in step on a cadence (#48)
- [x] P5.5 Define the release cadence and the patch policy (#49)
- [x] P5.6 Write the maintainer and handover guide (#50)

## Phase 6: Performance and scalability

Parent issue: #60
Branch: `feature/p6-performance`
Status: complete

Goal: make the simulator, the spatial metrics, and the route model fast enough that the metaheuristic
optimizer can evaluate thousands of candidate schedules on a C5-class dataset within a practical
budget. Plan of record: `notes/design/ws4-performance.md`.

- [x] P6.0 Benchmark harness and baseline (#61)
- [x] P6.1 Route and simulation quick wins (#62)
- [x] P6.2 Vectorized simulator core (#63)
- [x] P6.3 Spatial precompute and incremental metrics (#64)
- [x] P6.4 Incremental objective evaluation (#65)
- [x] P6.5 Solvers at scale (#66)
- [x] P6.6 Native kernels (#67) — adopted (product-gather kernel)
- [x] P6.7 Guardrails (#68)
- [x] P6.8 Shared age-grid curve table (#69)
- [x] P6.9 Fast fragment-to-feature join rebuild (#70)
- [x] P6.10 Incremental route accounts (#71)
- [x] P6.11 Faster simulator construction (#72)
- [x] P6.12 Faster route-record accumulation (#73)
- [x] P6.13 Adjacency-scoped spatial constraints (#74)
- [x] P6.14 Faster matrix builder (#75)
- [x] P6.15 Score product accounts (#76)
- [x] P6.16 Live target-window watcher (#77)
- [x] P6.17 Multi-rotation schedules in the optimizer (#78)
- [x] P6.18 Move-based incremental objective (#79)
- [x] P6.19 Patch size-distribution targets (#80)
- [x] P6.20 Topology cluster operator
- [x] P6.21 Stand-centred opening constraints in the MIP bound
- [x] P6.22 Adaptive temperature schedule
- [x] P6.23 Target-weight calibration
- [x] P6.24 MIP bound on the command line
- [x] P6.25 Patch-account evaluation bottleneck (profiled; early-exit and label fixes landed)
- [x] P6.26 Patch accounts: correct the membership and the default search distance
- [x] P6.27 Make the criterion-series primitive cheap (patch `_affected`)
- [x] P6.28 Compiled-port ceiling measured on realistic components (decision; prototype only)
- [x] P6.29 Array-backed patch state with a compiled bulk relabel
- [x] P6.30 Compiled connectivity walks (recovers the single-block regression)
- [x] P6.31 Stale components reported by the relabel; spanning-forest leaf test measured and rejected
- [x] P6.32 Binding patch benchmark and the gap/merge operator
- [x] P6.33 Split operator; volume-floored benchmark corrects the operator claim
- [x] P6.34 Multiple target windows in `ws4 watch`
- [x] P6.35 Patch statistics only at the accounting periods (5x on the patch benchmark)
- [x] P6.36 A period-spanning patch target is read at one year of the period
- [x] P6.37 State the time-step model (simulation 1 year; account period a whole number of years)
- [x] P6.38 Watch the target windows side by side
- [x] P6.39 Weighted term display, side-by-side windows, and the warm-start/ceiling finding
- [x] P6.40 Number accounting periods from 1 (period 0 is the pre-simulation state)
- [x] P6.41 Flow targets (`flow: even`, `flow: ndy`)
- [x] P6.42 Correct the flow definitions (reference-period percent difference; ndy between periods)
- [x] P6.43 Price flow targets per period; fix the watcher's flow display
- [x] P6.44 Docs audit: correct the stale page claims and complete the `ws4.opt` docstrings
- [x] P6.45 Public-docstring audit and the `docstrings` dashboard gate
- [x] P6.46 Verify the flow definitions against the established specification
- [x] P6.47 Consolidate the repository's commit authorship and refresh the citations
- [x] P6.48 Documentation for human users: getting started, task guides, and an examples gallery

Deferred from P6, triaged in `notes/backlog.md`:

- (none outstanding: P6.6 is decided — adopted as a numba product-gather kernel, ~1.1× end-to-end;
  see `notes/design/ws4-performance.md` (WP6 status).)

Acceptance criteria:

- C5 30-year `simulate` under 1 s; 3-year `simulate` plus routing under 5 s.
- Patch accounts, edge contrast, and core area per year under 0.2 s.
- One optimizer objective evaluation on C5 under 50 ms (incremental).
- Near-linear scaling to 32+ cores; reproducibility preserved.

## Phase 7: Parity and the analyst workflow

Parent issue: #82
Branch: `feature/p7-parity`
Status: complete

Goal: make the replacement claim checkable and the tool comfortable to use all day: close the gaps the
Phase 6 close-out recorded, put the workspace in step with the tooling, and extend the documentation
where a new analyst needs it.

- [x] P7.1 Close the command-line gaps: `--weights` and `--iterations` (#83)
- [x] P7.2 Apply the `threads` setting and re-measure island scaling (#84)
- [x] P7.3 Ship a sample estate under `examples/` (#85)
- [x] P7.6 A patch target in a search misprices the classes (#88)
- [x] P7.4 Add the patch, route, and sweep notebooks, and a concepts section (#86)
- [x] P7.5 Patch performance under a dense harvest (#87)

Deferred from P7, triaged in `notes/backlog.md`:

- (none outstanding.)

Acceptance criteria:

- Both command-line gaps closed, with tests.
- `threads` applied, and the island scaling measured on an idle host.
- The sample estate used by at least one guide and one notebook.
- The docs build and the docstrings gate green, with the dashboard green at every commit.

## Phase 8: Verify the replacement claim

Parent issue: #90
Branch: `feature/p8-verify`
Status: complete

Goal: demonstrate the claim the project exists to support — that WS4 is a working replacement for the
established tool — instead of asserting it, by exercising WS4 against the reference implementation's
own outputs and against the figures the earlier phases recorded.

- [x] P8.1 Build a parity harness against the reference outputs (#91)
- [x] P8.2 Reproduce the C5 results from documented inputs (#92)
- [x] P8.3 Speed up the criterion series and the patch-state construction (#93)
- [x] P8.4 Measure island scaling on a controlled host (#94)
- [x] P8.5 Compare WS4's accounts against a reference report (#95)

Deferred from P8, triaged in `notes/backlog.md`:

- the accounts comparison against a reference report (#95): built, tested and documented, and blocked on
  an export from a licensed Windows run. Carried to Phase 9 and re-linked as a sub-issue of its parent
  at that launch.

Acceptance criteria:

- A parity comparison a reviewer can run and read, with the differences it found either fixed or
  explained.
- The C5 patch and flow results reproducible from inputs documented in the repository.
- The criterion-series work judged against the P7.5 baseline, with the measurement recorded.
- Island scaling measured with the host's load recorded, and the memory-traffic question answered.
- The dashboard green at every commit, with the docs and docstrings gates.

## Phase 9: Spatial performance and memory

Parent issue: #97
Branch: `feature/p9-memory`
Status: complete
Pull request: against `main`, carrying Phase 10 with it — Phase 10 was stacked on this branch and merged
into it (`b512cd9`) when the maintainer approved it, so the two phases reach `main` together.

Goal: act on what Phase 8 measured. P8.4 established that island scaling stops being near-linear because
of the memory hierarchy — not BLAS, not the per-process setup, not SMT, each excluded by measurement —
and found the concrete reason a shared dataset would not help as things stand: every process loads its
own copy before doing anything, and the simulator writes to the fragments frame it inherits.

- [x] P9.1 Share the dataset across worker processes (#98)
- [x] P9.2 Re-measure island scaling with the dataset shared (#99) — measured and rejected; #98 reverted
- [x] P9.3 Make the patch-state construction cheaper (#100) — the group topology is shared across years
- [x] P9.4 Stop rebuilding bounds in every curve gather (#101)
- [x] P9.5 Compare WS4's accounts against a reference report (#95, carried from P8) — **PASS** on both 2026 scenarios, 1,323 account-period values reproduced
- [x] P9.6 Put the package under the type gate (#102) — the gate checked 50 files, it now checks 93
- [x] P9.7 Check growth against the reference's own yields (#103) — 959 yield-curve points reproduced; one conflict in the sample's own files, recorded
- [x] P9.8 The matrix builder mis-attributes a split block's track (#110) — fixed; 30-45% on every managed/unmanaged account

Deferred from P9, triaged in `notes/backlog.md`:

- (none outstanding.)

Holding on an external input:

P9 stays **active** until P9.5 lands, rather than deferring it a second time. It needs an export from a
licensed Windows run of the reference: `schedule.csv` (one row per decision: block, treatment, year) and
`account_values.csv` (one row per account per period), replayed in WS4 by
`python scripts/acceptance.py --accounts-report <export> --accounts-dataset <compiled c5>`. The
comparison, the export specification and what it does *not* cover are in
`notes/design/ws4-parity-harness.md`. The sample to run it on is packaged beside the workspace as
`c5-sample-for-parity.zip` with 139 per-file digests in `c5-sample-for-parity.sha256`; the archive
verifies against them.

Acceptance criteria:

- The dataset is shared across workers, or there is a measured reason it cannot be.
- Island scaling re-measured at a recorded load, compared against P8.4's 17.7x at 55% efficiency.
- The patch-state and curve-gather costs judged against the P8.3 profile, with the measurements recorded.
- The dashboard green at every commit, with the docs and docstrings gates.

## Phase 10: Documentation and the API-first workflow

Parent issue: #104
Branch: `feature/p10-docs-api`
Status: complete
Pull request: #109, squash-merged as `b512cd9` into `feature/p9-memory`, the branch it was stacked on.
It reaches `main` with Phase 9's close-out, since the two are one line of history now.

Goal: serve the second audience in the gallery, and stop the gallery being able to lie. The prose for
the Python API exists; the examples do not — five of seven notebooks drive the command line — and the
notebooks' outputs are committed with ``nbsphinx_execute = "never"``, so nothing checks that what they
show is what the code does.

- [x] P10.1 An API-first walkthrough notebook (#105) — `examples/070_library_path`, executed
- [x] P10.2 Prove the gallery's outputs are current (#106) — `scripts/check_notebooks.py`, its own CI job
- [x] P10.3 Say which way in each example takes (#107)
- [x] P10.4 Price a periodic target over its period in the report (#108) — found by P10.1

Deferred from P10, triaged in `notes/backlog.md`:

- (none outstanding.)

Holding on a design question, recorded rather than fixed:

- **Flow targets in `report_targets.csv`** are still mis-reported: `target_status` prices every target as
  a level target over its period, while the objective prices a `flow` target as a per-period percent
  series. Measured in P10.4: an `ndy` target with `minimum: -1` over a series dropping 100 -> 60 is
  priced at **39.00** by the objective and reported as `met` with **0.00**. Fixing it means deciding
  what the report should show for a flow target, which is a design question; it is in
  `notes/backlog.md` with the numbers. The sample estate's own targets are level targets, so nothing
  shipped is affected.

Acceptance criteria:

- A complete API-first session runs as a notebook in the gallery, executed, linked from the API pages.
- A documented command re-executes the notebooks and reports drifted output, and it can fail.
- Every example states whether it is a command-line session or a library one.
- The dashboard green at every commit, with the docs and docstrings gates.

## Phase 11: The derived targets and the sample's own files

Parent issue: #112
Branch: `feature/p11-derived-targets`
Status: complete
Pull request: #119, squash-merged as `0d34412`.

Goal: close the gap between the accounts comparison passing and the replacement claim being whole.
Phase 9 verified WS4's plain account values against the 2026 reference on both of its scenarios and
named **178 reference targets it could not compare** — ratios, flow constraints, and patch size and
age-class distributions — because they are derived quantities rather than account values. Those are
what a spatial model is for. This phase gives them definitions on WS4's side, matches WS4's period
convention to the reference's, and repairs the three sample-side gaps Phase 9 uncovered.

- [x] P11.1 Match the reference's period convention (#113)
- [x] P11.2 Compare the derived targets: the ratios (#114)
- [x] P11.3 Compare the derived targets: the flow constraints (#115) — values matching the reference to four decimals; the report fixed
- [x] P11.4 Compare the derived targets: the patch size and age-class distributions (#116) — 630 cells over six quantities; the stops measured
- [x] P11.5 Give the routing parity check the model's mill set (#117)
- [x] P11.6 Retarget the growth check for the 2026 sample (#118)

Deferred from P11, triaged in `notes/backlog.md`:

- (none outstanding.)

Direction (maintainer, mid-phase): **verified parity first.** Match the reference's semantics and prove
it against its own reports; only from that base is WS4 free to redefine how something is calculated,
justified and documented, and a parity mode that enforces the reference's readings is the natural home
for those deliberate divergences.

Acceptance criteria:

- A target written the reference's way means the same thing in WS4, verified against the reference's own
  period values.
- Each family of derived targets is either compared and agreeing, or has a measured reason and a
  recorded definition gap.
- The routing parity check compares against the model's actual destinations.
- The growth check reads the 2026 sample's shape and passes on it.
- The dashboard green at every commit, with the docs and docstrings gates.

## Phase 12: Spatial decision match

Parent issue: #120
Branch: `feature/p12-spatial-decisions`
Status: complete

Close-out report: `notes/reports/p12-closeout.md`.

Goal: take the replacement claim from "the account values and the routes match" to "the **spatial
decisions** match". Phase 11 verified the values — 1,383 account-period and flow values reproduced on
both 2026 scenarios, routing parity on all 25,134 pairs, 959 yield-curve points, and a patch family
compared over 630 cells — and named the places where the reference makes a decision WS4 does not, each
measured: a patch criterion cannot be a product, the reference's mill products are allocated by its own
policy rather than WS4's least-cost routing, and the five `attractor` cells report a quantity WS4 does
not have.

- [x] P12.1 A patch criterion can be a product (#121) — refused with its reason measured; the real fix is the treatment's timeline
- [x] P12.2 The reference's destination policy for mill products (#122) — its declared destinations, then least haul cost; the delivery target left to the parity mode
- [x] P12.3 Report the route accounts over the model's periods (#123) — the report folds into the model's periods, per destination too
- [x] P12.4 The attractor sub-account as the reference defines it (#124) — established as a per-patch quantile the export does not determine; refused, not faked
- [x] P12.5 A Patchworks-parity mode, with traffic-weighted maintenance behind it (#125) — parity by default, one named divergence, its effect measured
- [x] P12.6 Compare the patch components against a reference membership export (#126) — the comparison is built and tested, WS4 states its own components, and the class aggregates are recorded as the ceiling: the reference cannot export membership

Deferred from P12, triaged in `notes/backlog.md`:

- The patch criterion on the treatment's own timeline, patch membership (the ceiling: this reference
  cannot state it), the reference's Mill 1 delivery target, what its route report `LENGTH` counts, and
  the route report's distance unit. Each names its blocker.

Acceptance criteria:

- The reference's harvested patch family is compared, or has a measured reason it cannot be.
- The mill products' split is decided the same way in both tools, and the route ratios compared.
- The route report states the model's period width, and its columns are comparable per period.
- The attractor is reported as the reference defines it, or the difference is measured.
- A parity mode exists that enforces the reference's readings, with each deliberate divergence named and
  its effect documented.
- The dashboard green at every commit, with the docs and docstrings gates.

## Phase 13: The reference's remaining readings

Parent issue: #128
Branch: `feature/p13-reference-readings`
Status: complete

Goal: close the parity items P12 deferred — each one either implemented, or refused again with a sharper
measurement. They are the places where the reference's reading is known to differ *and* the comparison is
blocked on something WS4 computes: the patch criterion on the **treatment's own timeline** (the harvested
family is 28 of its 63 patch targets, and its values land ten years late), the reference's **Mill 1
delivery target** (what is left of its mill-product split), and the route report's **distance unit**. Two
further items cannot be closed against this reference and are recorded rather than tasked: patch
**membership** (the ceiling P12.6 established) and what its route report **`LENGTH`** counts, where two
more readings of the export have been ruled out.

- [x] P13.1 A patch criterion that is a product, on the treatment's own timeline (#129)
- [x] P13.2 The reference's delivery target for its mill products (#131) — implemented and measured not
  to close the split: its numbers are a search outcome under soft bounds, and WS4's rule is already
  91.7% of the way there — the mechanism implemented and the harvested family compared, agreeing in aggregate (area 0.92, count 1.48) and accepted; 28 of the reference's 63 patch targets are now comparable

Acceptance criteria:

- The harvested patch family is compared and agreeing, or has a measured reason it cannot be, with a
  feature criterion's patch accounts unchanged throughout.
- WS4's mill products are decided the way the reference decides them, or the difference is named with its
  measurement, and the route ratios are compared or their remaining gap named.
- The route report states its distance in a unit it names.
- The dashboard green at every commit, with the docs and docstrings gates.

## Phase 14: Optimizer search for aggregate targets

Parent issue: #133
Branch: `feature/p14-optimizer-seeding`
Status: complete

A second phase is active while P13's last item (the route report's distance unit) waits on a maintainer
decision: the maintainer directed this work, and it is not P13's subject.

Goal: make the optimizer find **aggregate, narrow-window treatment targets** — a treatment offered on few
blocks in few years, a floor on a product account, and a ceiling on a cost account. On the TSA23
fuel-treatment instance a trivial greedy reaches **penalty 0** where `ws4 optimize` reaches **15,758**
with 335 ha treated against a 16,000 ha floor and a $200M ceiling, because the generic operators move one
random block at a time and ~290 treatment moves are a needle in a haystack. `warm_start=True` seeds every
block's first candidate chain, which ignores the ceiling and over-schedules. One measured defect is in the
way: `--time-limit` is accepted and never read.

- [x] P14.1 A greedy, constraint-aware initial schedule (#134)
- [x] P14.2 Make --time-limit do what it says (#136) — enforced in the four solvers, refused when
  malformed, and reported as `time_limit_reached`

Acceptance criteria:

- On a small synthetic model with an aggregate account floor and a cost-account ceiling, the optimizer
  reaches the floor without breaching the ceiling where the current behaviour does not, and a test
  exercises exactly that, failing at the commit before the change.
- The mechanism names no model, no account label, and no treatment.
- No regression in the parity acceptance checks, and `python scripts/dashboard.py` green.
- The TSA23 instance is not on this machine, so that criterion is left to the maintainer with the recipe.

## Phase 15: A spread-connectivity account

Parent issue: #138
Branch: `feature/p15-spread-connectivity`
Status: complete

Goal: a spatial account that measures **how fragmented the fuel body a fire could run through is**, so a
fuel-treatment schedule can be optimized against fire-spread response inside WS4. The patch-size
accounts cannot carry it: on equal-area patterns a wind-perpendicular barrier burns least (19,640 ha)
yet has the largest large-patch share (40.2%), so a large-patch target penalizes the arrangement that
works.

- [x] P15.1 The spread-connectivity account and its synthetic oracle — the compartment over the fast edges, an oracle where the patch-size account is blind (same largest patch) while a full-span band fragments (210 ha) and a partial one does not (450 ha), and the rework that followed running the real bridge instance
- [x] P15.2 Wire it into the simulator and the optimizer — per-year in a run, whole-schedule in the optimizer, and declarable from the CLI
- [x] P15.3 Document it, and state what the bridge test still has to confirm — `docs/reference/spatial.rst`, `simulator.rst`, `optimizer.rst`, and the design note

Acceptance: a synthetic test where the patch-size account cannot rank two equal-area full-span bands,
while the compartment measure separates a full-span band from a partial one. The bridge clause is
**withdrawn**: the compartment did order the patterns as the fire model did at its original 177,088 ha
treatment, but a matched-footprint rerun at the ~54,000 ha WS4 can treat reverses the mean order and
finds the gaps inside seed noise (P16.1, `notes/reports/p16-bridge-matched.md`). The account remains a
defined fragmentation metric with no demonstrated fire-response relationship at that footprint.

What the bridge cannot yet settle, and the phase reports rather than claims:

- the fire model treats 177,088 ha of whole scheduled blocks, while WS4's FT product reaches ~46,600 ha
  of managed fragments — the two sides are not the same intervention;
- the fire spread between patterns is 3%, on one stochastic seed;
- the directed reading that the first oracle pinned does not survive the real map (its largest
  component was a boundary corridor common to all three patterns);
- an orientation-aware measure needs anisotropic rates and a burn duration, which is a fire model
  rather than an account.

## Phase 16: The bridge at the same footprint

Parent issue: #141
Branch: `feature/p16-bridge-matched`
Status: complete

Goal: close the two gaps P15 left. First, the bridge ranking was measured on a different
intervention: the fire model treats 177,088 ha of whole scheduled blocks, while WS4's FT product
reaches about 46,600 ha of managed fragments. Repeat the fire model on the WS4-treated masks across
five seeds and report whether the ranking survives. Second, the product table can carry the same
`(track, treatment, label)` key more than once; the simulator records every row, so the account is
multiplied — 4.0000 times for `product.Treated.managed.FT` in the TSA23 FT dataset, and two to four
times for the SpeciesProp, Yield and HarvestedVolume families. Make the builder emit one row per key
and curve, and make the loader say so when a dataset does not.

- [x] P16.1 Run the fire model on the WS4-treated masks across five seeds — done locally with the
  instance's own functions: five seeds per pattern, 54,368 / 55,837 / 53,697 ha treated. The published
  ranking **does not survive**; the mean order reverses and the largest gap (0.38%) is inside the seed
  range (15%). Report: `notes/reports/p16-bridge-matched.md`. The independent rerun in
  `UBC-FRESH/femic-tsa23-instance` #11 reproduces all fifteen values to four decimals.
- [x] P16.2 One product row per `(track, treatment, label)` and curve, and a loader that names a
  dataset that repeats one — the builder drops exact duplicates and keeps a repeated key with
  different curves (a sum of components); `Simulator.from_dataset` warns with the count and the
  affected labels; `ws4/model/checks.py` and `tests/test_dataset_checks.py` pin both.
- [x] P16.3 Record the account's final scope — the compartment over the fast edges, direction in the
  cone, and the orientation limit, in `docs/reference/spatial.rst` and the design note.

Acceptance: the matched-footprint ranking across seeds, a dataset with a repeated product row that
cannot be simulated without a named warning, a fresh compile with no repeated row, and the dashboard
green.

## Phase 17: Roads opened to the period

Parent issue: #145
Branch: `feature/p17-opened-roads`
Status: complete

Goal: route each period over the roads that exist in it. The reference routes only through segments
built on or before the current period and builds new ones during the solve to reach the blocks it
selects; WS4 routes over the whole planned network, using 2.6× (MILL 1) and 3.3× (MILL 2) the road the
reference reports while hauling cheaper. Per-segment parity is not required, but the accounting —
`LENGTH`, `BUILTLENGTH`, build expense, maintenance and haul — should match as closely as the model
allows. **A build unit cost of 0 is a hard-coded trigger to build in period 1**, not a marker of an
existing road. The model therefore starts with no opened segment, opens a planned segment when a
selected block first needs it, and books a zero-cost segment's build at the first period it is needed;
the initial open set is a parameter fitted against the reference's period 1 (`LENGTH` 1,149,647,
`BUILTLENGTH` 732,073, `BUILD_EXPENSE` 3,660,367 — so the 24,273 zero-cost segments totaling 4.4M m are
not all built then).

- [x] P17.1 Openness and routing — an opened set initialised from the existing segments; routes over it;
  the least-haul full-network path opens planned segments on demand; caches keyed by the open version.
- [x] P17.2 Accounting — `BUILTLENGTH` charged when opened, `LENGTH` over opened segments used,
  maintenance once per used segment per period; the 2026 sample compared per period.
- [x] P17.3 Tests — a synthetic existing road plus a block beyond it; one build charged once, reused next
  period; an opened road preferred over a cheaper unopened one.
- [x] P17.4 Measure and record — the per-period ratios and the early build spike against the reference.

- [x] P17.5 The maintenance charge — the ledger charged it per year and the report summed the period;
  the reference charges once per period. Charging once over the period's union gives **1,052,489**
  against the reference's 1,126,465 (0.93×), where the per-year sum was 3,622,033 (3.22×). The charge is
  booked in the first year of the period in which the segment is used.
- [x] P17.6 The road/haul trade-off — measured: build cost **per metre is identical** (5.00 both), the
  reference builds 1.9× more; WS4 hauls 22% farther but on roads 0.46× the cost per unit-km. It is a
  **model-objective difference** (WS4 minimises haul over roads that exist; the reference solves the
  road set and assignment jointly), recorded as the second named divergence rather than tuned with an
  uncalibrated road price. Report: `notes/reports/p17-tradeoff.md`. The route report's
  `AVERAGEHAULDIST` is now in kilometres, closing the last P13 item.

Acceptance: the tests fail on whole-network routing and pass on opened routing; the 2026 `LENGTH` ratio
moves toward 1 with an early `BUILTLENGTH` spike; the remaining gap is measured; dashboard green. **The
first measurement is in `notes/reports/p17-opened-roads.md`:** dating halves the period-1 build expense
but moves `LENGTH` only 4.5%, so P17.5 is the remaining lever and the phase stays active.

## Phase 18: A graphical web front end

Parent issue: #146
Branch: `feature/p18-web-frontend`
Status: complete

Goal: a browser front end over the same artefacts the CLI writes — the compiled dataset, the schedule,
the account values, the route, patch and spread reports, the run summary — with a map, a period selector,
a targets panel and reports. Four skins (model builder, scenario analyst, scenario browser, reviewer) are
manifests over one application, not forks. The reference UI's layout is the inspiration: a layer tree with
grouped legends, a period strip, and Legend/Targets/Reports/Comparisons tabs; treatment maps separate the
current period from the cumulative total.

- [x] P18.1 The service surface — optional `ws4[web]` (FastAPI), artefacts as the contract, SSE for live
  incumbent values, targets round-tripping the optimizer's own YAML.
- [x] P18.2 The map shell — **first cut live**: a dependency-free SVG shell over the service, with a run
  selector, year control from the schedule, treated/untreated layers with counts, click selection,
  wheel-zoom/pan, and the Legend/Targets/Reports tabs. **First slice of the layer tree:** current and
  cumulative treatments, patch size classes from `patch_membership.csv`, and a grouped tree that
  names roads and spread compartments as unavailable. **Block polygons:** the map now uses the
  simplified source `blocks.shp` layer, with boundary strokes, solid/hatched fills and per-patch
  colours; the service caches the geometry, and live schedules update only the changed blocks.
  Source attributes (compartment, THEME2, THEME5, MartStrata, LMU) drive an optional base-colour
  mode with a category legend. An optional **source access-road overlay** reads `--roads` and draws
  the access network. P19.1 and P19.2 add the model spread-compartment membership and the run's
  used-road overlay; P19.4 adds MapLibre and the basemap, with the SVG shell kept as the fallback.
- [x] P18.3 Targets — **live**: a table per account and period with editable min/max/weights, a save
  that validates through the optimizer's loader, the realized value from the selected run's own CSV
  with a met/below/above status, and a **Run search** action that starts the optimizer behind
  ``--allow-runs``, streams progress over SSE, and refreshes the run when the summary lands. The
  **On** toggle writes ``active`` to the YAML; an inactive target is reported as ``inactive`` but not
  priced by the objective or the incremental evaluator.
- [x] P18.4 Reports — **live**: the report tree from the run directory, a CSV preview table, direct
  links for HTML/PNG, a named standard-report list (account/target/route/patch/spread/network/
  schedule), and a **Build a report** form over accounts and years with a CSV export.
- [x] P18.5 Skins — **live**: four checked manifests (`model-builder`, `scenario-analyst`,
  `scenario-browser`, `reviewer`), served at `/api/skins`, a selector in the shell, panel/layer hiding,
  and the read-only rule enforced in the loader (a read-only skin cannot carry a mutating action).
- [x] P18.6 Comparison — two runs side by side, map and account deltas, target status. The Compare
  tab reads both runs through the existing map, accounts and targets endpoints; the map colors
  A-only/B-only/both, the target table shows each run's period value and status, and the account
  table is sorted by absolute delta and filterable.

Acceptance: a session loads a dataset and run, shows the source-layered families and moves through the
horizon; a target edit round-trips and a re-solve matches the CLI's penalty; a report renders from the
run's CSV; the reviewer skin cannot edit; the CLI is unchanged without the extra; the dashboard is
green; the design is recorded before the first UI line. Close-out report:
`notes/reports/p18-closeout.md`; the model-derived layers are recorded in `notes/backlog.md`.

## Phase 19: Model-derived spatial layers and map scale

Parent issue: #161
Branch: `feature/p19-spatial-layers`
Status: complete

Goal: finish the model-derived spatial layers the P18 close-out deferred, and keep the map usable at
scale. The source polygons, source compartments and source access roads already ship; this phase adds
what the model produces.

- [x] P19.1 **Spread-compartment membership.** Write `spread_membership.csv` from the
  spread-connectivity account (year, account, compartment, class, block, area, component area); serve
  it as `layer=compartments`; add the model spread layer to the layer tree with class checkboxes and
  an account selector. This is the account independently reproduced in thesis #13.
- [x] P19.2 **The run's used-road geometry/use.** Write the route model's segment geometry and the
  period's opened/used segments; serve a used-roads overlay distinct from the source access layer.
- [x] P19.3 **Stability stopping criterion.** Stop a continuous search after a configurable number of
  iterations without incumbent improvement; expose it in the player and record it in the summary.
- [x] P19.4 **Map scale.** Move the polygon/road shell to MapLibre (or an equivalent) when the
  feature count or a basemap demands it, with the layer tree contracts unchanged.
- [x] P19.5 **Period map control.** Fold years by the targets' ``period_width``, label the map with
  the period and its year range, send the period range to the current/cumulative layers, and page
  with left/right arrow keys. This is the period control the P18 design named.
- [x] P19.6 **Resizable assistant pane.** A drag bar sizes the lower-left assistant, persisted in
  local storage and reset by double-click, so a conversation can use more of the sidebar.

Acceptance: a spread run writes the membership and the layer renders it; a route run writes segment
geometry/use; a stability stop writes the usual summary and names the criterion; the dashboard is
green on every merge; source layers are never mislabelled as model layers.

## Phase 20: Production map serving

Parent issue: #183
Branch: `feature/p20-map-lod`
Status: complete

Goal: keep the map usable on real management units by loading only the current viewport and only the
detail that zoom requires, instead of one full-management-unit GeoJSON payload.

- [x] P20.1 Add viewport bbox and zoom LOD to the map endpoint and UI (#184)
- [x] P20.2 Add the MVT tile endpoint and tile cache (#186)
- [x] P20.3 Add the MapLibre vector source and validate it in a browser (#187)
- [x] P20.4 Add the durable tile cache and 1M-fragment scale gate (#188)
- [x] P20.5 Close out production map serving (#189)
- [x] P20.6 Restore exact block geometry at detail zooms (#197)

Acceptance: a low-zoom request returns compact centroids, a high-zoom bbox request returns only the
visible blocks, the front-end reloads on `moveend` without a loop, and the TSA 46 initial payload is
below 20 MB.


## Phase 21: Search quality and validation

Parent issue: #190
Branch: `feature/p21-search-quality`
Status: complete

Goal: make the optimizer's quality measurable and improve it with small, evidence-backed changes.

- [x] P21.1 Add search reversion to SA, tabu, and ILS (#191)
- [x] P21.2 Add the multi-seed and multi-engine validation harness (#192)
- [x] P21.3 Add the target sensitivity report (#193)
- [x] P21.4 Add a threshold-accepting engine (#194)

Acceptance:

- `--reversion N` resets the current solution to the best every N accepted moves and the summary records it.
- `validate-search` reports best/mean/median/worst, standard deviation, feasibility rate, and the MIP gap when enabled.
- The sensitivity report names binding targets, slack, and the marginal effect of relaxing each target.
- The threshold engine shares the existing operators and evaluator.
- `python scripts/dashboard.py` is green.

## Phase 22: Map operations

Parent issue: #198
Branch: `feature/p22-map-ops`
Status: complete

Goal: make production map serving operationally repeatable: pre-warm the durable tile cache, prove the
service works behind a path prefix, and measure the 1M-fragment cold-build memory.

- [x] P22.1 Add the durable tile-cache pre-warm command (#199)
- [x] P22.2 Add the path-prefix deployment check (#200)
- [x] P22.3 Add the 1M-fragment peak-RSS profile and budget (#201)

Acceptance:

- A pre-warm run writes durable tiles and reports hits, misses, bytes, and time.
- The path-prefix check serves `/prefix/`, static assets, the API, and a tile.
- The 1M-fragment benchmark reports peak RSS and enforces the recorded budget.
- `python scripts/dashboard.py` is green.

## Phase 23: Accounts and target activation

Parent issue: #206
Branch: `feature/p23-target-browser`
Status: complete

Goal: let a user discover every account the run reports and activate any of them as an objective target
without knowing the account vocabulary in advance.

- [x] P23.1 Web UI: navigate every account and activate any as a target (#195)
  - [x] Read the run's account catalogue instead of a hard-coded list
  - [x] Group and search account names on their `.` segments
  - [x] Show the last value, level/flow, and existing-target state
  - [x] Add and remove targets through `/api/targets.json`
- [x] P23.2 Make Solve continuous and remove the media controls (#224)
- [x] P23.3 Fit the MapLibre view to the configured geometry (#226)
- [x] P23.4 Show current objective and accepted moves in the run panel (#232)

Acceptance:

- A user can find an account by substring and add a minimum, maximum, or both.
- Every account in the run's `account_values.csv` is reachable.
- The new target is written to the targets YAML and appears in the Targets table.
- An already-targeted account is visibly marked.
- `python scripts/dashboard.py` is green.

## Phase 24: Search portfolio and multi-objective

Parent issue: #207
Branch: `feature/p24-search-portfolio`
Status: complete

Goal: make the search's quality visible across objectives and tuned configurations: keep an elite
archive, run a portfolio over target-weight vectors to produce a Pareto front, add a repeatable
tuner, and expose true LP dual/reduced-cost sensitivity for the linear subset.

- [x] P24.1 Add the elite archive and Pareto front (#208)
- [x] P24.2 Add the portfolio runner over target-weight vectors (#209)
- [x] P24.3 Add the grid/random tuner (#210)
- [x] P24.4 Add LP dual and reduced-cost sensitivity (#211)

Acceptance:

- An archive keeps nondominated elites under named max/min metrics and exports schedules.
- A portfolio run varies target weights, records every member, and writes a front table.
- A tuner run ranks configurations by a stated budget and seed set.
- The LP relaxation reports finite target duals and option reduced costs on a small instance.
- `python scripts/dashboard.py` is green.

## Phase 25: Constraint repair and flow ceilings

Parent issue: #214
Branch: `feature/p25-constraints`
Status: complete

Goal: make hard feasibility explicit and auditable: let a run reject or repair infeasible
moves instead of only pricing them, report what happened, and add a constructive
binary-search flow ceiling under the active spatial rules.

- [x] P25.1 Add the constraint strategy guard and per-strategy counts (#215)
- [x] P25.2 Add the feasibility summary block and constraint report (#216)
- [x] P25.3 Add the binary-search flow-ceiling command (#217)

Acceptance:

- `reject` and `repair` produce zero spatial violations on a constrained fixture.
- `penalize` behavior is unchanged, and an unknown strategy fails before the search.
- The summary records the strategy, proposed/rejected/repaired counts, and final feasibility.
- `scripts/max_flow.py` writes the ceiling, probe log, and best feasible schedule.
- `python scripts/dashboard.py` is green.

## Phase 26: Reproducibility and data quality

Parent issue: #219
Branch: `feature/p26-repro-quality`
Status: complete

Goal: make every run reproducible and its data limitations visible: write a complete run manifest,
summarize dataset quality and known gaps, and compare scenarios over the same landscape.

- [x] P26.1 Add the run manifest (#220)
- [x] P26.2 Add the data-quality block and report (#221)
- [x] P26.3 Add scenario comparison (#222)

Acceptance:

- Every run writes `run_manifest.json` with code, dataset, config, seeds, environment, and a
  reproduce command.
- Every run writes `data_quality.json` and a summary block that names checks and unknowns.
- `scripts/compare_scenarios.py` compares labelled runs and writes JSON/Markdown/CSV.
- `python scripts/dashboard.py` is green.

## Phase 27: Goal normalization and priority tiers

Parent issue: #227
Branch: `feature/p27-normalization`
Status: complete

Goal: make target weights comparable across goals: opt-in automatic normalization, priority
tiers, and raw/normalized deviation reporting while keeping the current weighted objective as
the default.

- [x] P27.1 Add automatic normalization and the scale report (#228)
- [x] P27.2 Add priority tiers and the priority-aware objective (#229)
- [x] P27.3 Report normalized deviations in the run and scenario tables (#230)

Acceptance:

- A target can set `normalization: auto`; the normalized penalty and scale are reported.
- Targets with different `priority` values use the priority-aware objective; default targets do not.
- Existing targets produce the same objective and report values.
- `python scripts/dashboard.py` is green.

## Phase 28: Inventory and flow ceilings

Parent issue: #233
Branch: `feature/p28-inventory`
Status: complete

Goal: make closing inventory and flow ceilings first-class report surfaces: label level/flow
targets, emit the final inventory, add an NDY/even constraint to the flow-ceiling probe, and
carry both through scenario comparison.

- [x] P28.1 Add target kind and the ending-inventory report (#234)
- [x] P28.2 Add the NDY/even flow-ceiling probe (#235)
- [x] P28.3 Compare ending inventory and flow across scenarios (#236)

Acceptance:

- `report_targets.csv` names level and flow targets; `ending_inventory.csv` and a summary block
  report the final values.
- A max-flow probe can require NDY or even flow and reports the worst change and feasibility.
- Scenario comparison carries ending inventory and flow status.
- `python scripts/dashboard.py` is green.

## Phase 29: MIP lane and exact small-instance validation

Parent issue: #238
Branch: `feature/p29-mip`
Status: complete

Goal: close the optimality loop on small instances: solve the option-selection model exactly,
compare it with the heuristic under the same targets, and carry LP/MIP gaps into validation and
scenario reports.

- [x] P29.1 Add the option-model MIP lane (#239)
- [x] P29.2 Add exact-vs-heuristic validation (#240)
- [x] P29.3 Carry LP/MIP gaps into reports (#241)

Acceptance:

- `ws4 solve-mip` writes a schedule, summary, target report, and explicit model status.
- The exact-vs-heuristic report compares actual target penalties and names the gap.
- `--lp-bound` records the LP bound and gap; scenario runs carry bound/gap fields.
- `python scripts/dashboard.py` is green.

## Phase 30: Live run surfaces

Parent issue: #242
Branch: `feature/p30-live-surfaces`
Status: complete

Goal: make the browser's live run view truthful for every solver path, and close the small
target-editor and report-surface gaps left by the P23 dogfood.

- [x] P30.1 Emit live snapshots from non-delta solvers (#243)
  - [x] Add the snapshot callback to the problem and whole-schedule solvers
  - [x] Wire the engine's account-value snapshot
  - [x] Add a solver test and a c5 live-stream check
- [x] P30.2 Complete the target editor fields (#247)
  - [x] Add `kind` to the target rows and strip it on save
  - [x] Add a compact detail line for normalization, priority, kind, and notes
  - [x] Make the run controls sticky
  - [x] Extend the target-browser check and backend tests
- [x] P30.3 Surface ending inventory and flow status (#248)
  - [x] Add the ending-inventory card and standard report entry
  - [x] Add the Compare ending-inventory table
  - [x] Add Kind to the Compare target table
- [x] P30.4 Handle legacy year/period runs (#255)
  - [x] Add the alias in the shared CSV reader
  - [x] Preserve the legacy year label
  - [x] Add an endpoint test for a legacy run

Acceptance:

- A c5 patch/route run updates its map and target cards before completion.
- The target table exposes normalization and priority; kind and notes follow.
- P28 reports appear in the run and comparison surfaces.
- A legacy run is refused or normalized with a specific message.
- `python scripts/dashboard.py` is green.

## Phase 31: Comparison map over MVT

Parent issue: #257
Branch: `feature/p31-compare-map`
Status: complete

Goal: render the Compare map from one vector tile carrying A, B, and both flags, so
two large runs no longer fetch both full GeoJSON viewports.

- [x] P31.1 Add compare MVT tiles and the vector compare view (#258)
  - [x] Add the compare tile and stats endpoints
  - [x] Use the vector source and a compare paint expression
  - [x] Pass the compare flag into block details
  - [x] Verify on c5 and keep the report tables ahead of the map

Acceptance:

- Compare requests MVT tiles, not the full A/B GeoJSON.
- A-only, B-only, and both use the existing compare colors.
- The summary counts come from compare-stats.
- `python scripts/dashboard.py` is green.

## Phase 32: Dataset provenance and limitations

Parent issue: #249
Branch: `feature/p32-provenance`
Status: complete

Goal: turn the P26 data-quality block from `unknown` into a reviewable provenance record for the
GBR instances: define a dataset provenance sidecar, expose it through `ws4 quality`, apply it to
TSA 46 and TSA 47, and publish the model limitations those records imply.

- [x] P32.1 Add the provenance sidecar and `ws4 quality` (#250)
- [x] P32.2 Apply the GBR provenance records and verify the P26 report (#251)
- [x] P32.3 Publish the model-limitations page and links (#252)

Acceptance:

- A dataset with a valid sidecar reports `ok`; a missing sidecar remains `unknown`.
- `ws4 quality --check` fails on a missing or invalid sidecar.
- TSA 46 and TSA 47 reports name inventory vintage, curve provenance, THLB provenance, and
  explicitly unknown imputation/coverage fields.
- The limitations page is linked from the provenance output and docs.

## Phase 33: Search artifact browser

Parent issue: #261
Branch: `feature/p33-search-ui`
Status: complete

Goal: give the portfolio, tuner, and LP artifacts a read-only browser surface over the
runs root.

- [x] P33.1 Add the Search artifacts tab (#262)
  - [x] Discover portfolio/tuning/LP artifacts under the runs root
  - [x] Render portfolio members/front and tuner ranking
  - [x] Add the search panel to every skin
  - [x] Verify on c5 and document the CLI launch path

Acceptance:

- A portfolio artifact shows members, objective, metrics, and the front.
- A tuning artifact shows the ranked candidates, best/median, and parameters.
- No artifacts shows a clear empty state and the CLI command to create one.
- `python scripts/dashboard.py` is green.

## Phase 34: Search launcher

Parent issue: #265
Branch: `feature/p34-search-launch`
Status: complete

Goal: let the Search tab start a portfolio or tuner job, watch it, and open the result.

- [x] P34.1 Add portfolio and tuner launchers (#266)
  - [x] Add portfolio/tuner launch endpoints under --allow-runs
  - [x] Add the status endpoint and console tail
  - [x] Add the Search tab forms
  - [x] Verify with a short c5 artifact
- [x] P34.2 Add cancellation and a bounded job list (#272)
  - [x] Add the stop endpoint and process termination
  - [x] Prune the job list on launch and completion
  - [x] Add the Search tab stop/list controls
  - [x] Add endpoint tests and verify on c5

Acceptance:

- A launcher writes a directory under the runs root and returns its id.
- Status reports running, done, or failed.
- A finished job opens in the artifact table.
- `python scripts/dashboard.py` is green.

## Phase 35: Instance provenance adoption

Parent issue: #267
Branch: `feature/p35-provenance`
Status: complete

Goal: make the P32 provenance result reproducible in the GBR instance repositories: track the
sidecar, apply it after the matrix build, link the limitations page, and gate the build with
`ws4 quality --check`.

- [x] P35.1 Track the sidecars and apply/check hook (#268)
- [x] P35.2 Link the limitations page in both instance docs (#269)
- [x] P35.3 Gate the full build with `ws4 quality --check` (#270)

Acceptance:

- A fresh build copies `data_quality.yaml` beside the matrix and passes the quality check.
- Both instance docs link the limitations page.
- The build exits non-zero when provenance is missing or invalid.
- `python scripts/dashboard.py` is green.

## Phase 36: Workflow conformance

Parent issue: #273
Branch: `feature/p36-conformance`
Status: complete

Goal: reconcile the P30-P34 planning surfaces after the UI work: exact issue templates,
one parent per phase, one child per task, close-out reports for completed phases, and
consistent roadmap/changelog statuses.

- [x] P36.1 Reconcile the P30-P34 planning surfaces (#274)
  - [x] Audit and reformat the affected parent and task issues
  - [x] Reopen P34 and add P34.2 as a child
  - [x] Write P31 and P33 close-out reports
  - [x] Sync roadmap and changelog
  - [x] Run the dashboard and read back the planning surfaces

Acceptance:

- The affected issues match the phase/task templates.
- P34 is active with P34.2 planned and linked.
- P31 and P33 have reports; P30's report reflects its merge.
- The roadmap/changelog statuses agree with merged state.
- `python scripts/dashboard.py` is green.


## Phase 37: FreshForge provenance gate

Parent issue: #278
Branch: `feature/p37-provenance-gate`
Status: complete

Goal: make the FreshForge lane enforce the P35 provenance gate: add `ws4 quality --sidecar`,
add a `femic.ws4_quality` provider, and wire it into both GBR instance workflows after
validation.

- [x] P37.1 Add `ws4 quality --sidecar` (#279)
- [x] P37.2 Add the `femic.ws4_quality` provider (#280)
- [x] P37.3 Wire both instance workflows and docs (#281)

Acceptance:

- `ws4 quality --sidecar PATH --check` installs the sidecar and gates the report.
- `femic.ws4_quality` builds the install/check command and is covered by a provider test.
- Both instance workflows add the node after validation and name the gate in docs.

## Phase 38: Instance FreshForge provider execution

Parent issue: #287
Branch: `feature/p38-provider`
Status: complete

Goal: make the GBR FreshForge workflows executable: package `tsa46.ws4` and `tsa47.ws4` providers with
the build, validate, schedule, and simulate nodes the workflows reference, then validate the graphs.

- [x] P38.1 Package the TSA 46 provider and tests (#288)
- [x] P38.2 Package the TSA 47 provider and tests (#289)
- [x] P38.3 Validate both workflows end to end (#290)

Acceptance:

- Each instance exposes its `tsaXX.ws4` provider through an entry point.
- The provider builds the expected commands for every workflow node.
- FreshForge validation resolves every node in both workflows.
- `python scripts/dashboard.py` is green in both instances.
## Phase 39: Account browser polish

Parent issue: #293
Branch: `feature/p39-account-polish`
Status: complete

Goal: finish the account browser and target-period labels so a user can read the full
account name, see search counts, navigate by keyboard, and distinguish the optimizer's
target period from the map's year range.

- [x] P39.1 Complete the account browser and period labels (#294)
  - [x] Render full names and the search count
  - [x] Add Enter/arrow navigation
  - [x] Change period labels to year ranges and the target header
  - [x] Add/update tests and browser verification
  - [x] Update the web reference and changelog

Acceptance:

- Full account names are visible.
- Search reports matched/total counts.
- The tree is keyboard-navigable.
- Map labels use year ranges; target rows say "Target period".
- `python scripts/dashboard.py` is green.

## Phase 40: Bounded provider workflow execution

Parent issue: #297
Branch: `feature/p40-smoke`
Status: complete

Goal: execute the provider graph on a bounded existing matrix, not only validate it: add a smoke
workflow from validate through provenance, schedule, and simulate, add a runner that registers the
local providers, and record the commands and artifacts.

- [x] P40.1 Add the smoke workflow and runner (#298)
- [x] P40.2 Execute both smoke runs and record evidence (#299)
- [x] P40.3 Document the smoke command and gate (#300)

Acceptance:

- Both smoke graphs execute every selected node successfully.
- The provenance node passes on the existing sidecar.
- The schedule and one-year simulation artifacts exist.
- The evidence JSON names the commands, statuses, and artifacts.

## Phase 41: Provider smoke in CI

Parent issue: #303
Branch: `feature/p41-ci-smoke`
Status: complete

Goal: run the provider graph automatically: add a tiny fixture build, pin the provider
environment, execute the full build → validate → provenance → schedule → simulate chain in each
instance's CI, and upload the evidence.

- [x] P41.1 Add the fixture and CI smoke workflow (#304)
- [x] P41.2 Pin the provider environment and run the smoke (#305)
- [x] P41.3 Upload evidence and document the gate (#306)

Acceptance:

- The CI smoke includes `build_dataset`, validate, provenance, schedule, and simulate.
- Every node succeeds on the tiny fixture.
- The evidence JSON is uploaded as a CI artifact.
## Phase 42: Target operations

Parent issue: #308
Branch: `feature/p42-target-ops`
Status: complete

Goal: add several accounts in one pass and make target replacement safer to review.

- [x] P42.1 Add multi-account target creation (#309)
  - [x] Add multi-select state and tree styling
  - [x] Show the selected-account summary
  - [x] Build one row per selected account
  - [x] Add browser verification
- [x] P42.2 Add target validation and a pre-save backup (#310)
  - [x] Add the browser validation helper
  - [x] Validate Add target and Save targets
  - [x] Write `targets.yaml.bak`
  - [x] Add endpoint and browser tests

Acceptance:

- Two or more accounts can be added in one save.
- Duplicate and invalid targets are blocked with named messages.
- The previous YAML is preserved as a backup.
- `python scripts/dashboard.py` is green.

## Phase 43: Search artifact depth

Parent issue: #330
Branch: `feature/p43-search-depth`
Status: complete

Goal: turn the Search tab into a review surface for Pareto members, LP sensitivity, and
failed runs, with safe artifact downloads.

- [x] P43.1 Pareto member drilldown and artifact downloads (#331)
  - [x] Artifact-relative paths and safe file endpoint
  - [x] Member detail panel
  - [x] Downloads for schedule/targets/front/report
- [x] P43.2 LP sensitivity view (#332)
  - [x] Discover `lp_sensitivity.json`
  - [x] Dual table
  - [x] Reduced-cost table
- [x] P43.3 Failure and metadata view (#333)
  - [x] Failure counts and error text
  - [x] Console link
  - [x] Budget/seeds/mode metadata

Acceptance:

- Front members are inspectable and downloadable.
- LP duals and reduced costs are readable.
- Failures and console output are visible.
- `python scripts/dashboard.py` is green.

## Phase 44: Comparison and map operations

Parent issue: #341
Branch: `feature/p44-compare-ops`
Status: complete

Goal: make the comparison path production-grade on large AOIs: durable compare tiles,
a browser smoke, and a cold/warm scale gate.

- [x] P44.1 Add durable compare tiles and pre-warm support (#342)
  - [x] Compare cache path and disk read/write
  - [x] Pre-warm compare layers
  - [x] Endpoint and prewarm tests
- [x] P44.2 Add the compare browser smoke and detail parity (#343)
  - [x] Browser smoke script
  - [x] Verify flags/counts/details
- [x] P44.3 Add the compare cold/warm scale gate (#344)
  - [x] Benchmark script
  - [x] Budget options and report

Acceptance:

- Repeated compare tiles hit disk.
- Pre-warm writes compare tiles.
- Browser smoke verifies flags and details.
- Benchmark records cold/warm and enforces budgets.
- `python scripts/dashboard.py` is green.

## Phase 45: Route evaluation performance

Parent issue: #368
Branch: `feature/p45-route-profile`
Status: complete

Goal: measure the current route evaluation and specify an incremental ledger before
changing optimizer accounting.

- [x] P45.1 Profile route evaluation and specify the incremental ledger (#369)
  - [x] Add the profiling script
  - [x] Run it on c5
  - [x] Write the invariants and API
  - [x] Document the profile command

Acceptance:

- A repeatable profile reports seconds per evaluation and top costs.
- The design note states fallback conditions and parity tests.
- `python scripts/dashboard.py` is green.

## Phase 46: Cached route event ledger

Parent issue: #382
Branch: `feature/p46-route-events`
Status: complete

Goal: remove the full simulator from route evaluations when the network is fully open and no
delivery target is set, by caching per-block route events and replaying the ledger.

- [x] P46.1 Cache block route events and replay the ledger (#383)
  - [x] Add the event method and refactor the block route chain
  - [x] Add the optimizer event cache and replay
  - [x] Route per-segment accounts through the replay
- [x] P46.2 Prove parity and gate the fallback cases (#384)
  - [x] Shared-segment build/maintenance parity
  - [x] Order and re-add parity
  - [x] Fallback gate tests
- [x] P46.3 Benchmark c5/GBR and close out (#385)
  - [x] Add the benchmark script
  - [x] Run c5
  - [x] Record the missing GBR route config as a deviation
  - [x] Write the close-out and docs

Acceptance:

- Incremental and full route values agree exactly on fixtures and c5.
- Delivery and opened-road configurations still take the full path.
- A repeatable benchmark reports cold and warm times.
- `python scripts/dashboard.py` is green.

## Phase 47: Model boundary record

Parent issue: #311
Branch: `feature/p47-boundary`
Status: complete

Goal: record the accepted GBR model boundary and publish a concise limitations page linked from
each instance's index, model-build guide, decisions page, and provenance sidecar.

- [x] P47.1 Add the model-boundary ADR (#312)
- [x] P47.2 Add the limitations page and links (#313)
- [x] P47.3 Link the provenance record and verify docs (#314)

Acceptance:

- Each instance has an accepted ADR naming the predecessor THLB, curve provenance, and AAC limits.
- Each docs site has a limitations page in the toctree.
- The model-build and decisions pages link it.
- Both instance dashboards are green.

## Phase 48: Ground-plot volume and DBH validation

Parent issue: #324
Branch: `feature/p48-ground-plots`
Status: complete

Goal: reconcile the independent FAIB/Nemora ground plots against the production TSR-consistent
curves, publish volume, DBH, height, and stems with sample sizes, and record a bounded decision.

- [x] P48.1 Reconcile the plot set and provenance (#325)
- [x] P48.2 Publish the stratified validation tables (#326)
- [x] P48.3 Record the validation decision and close out (#327)

Acceptance:

- Both instances trace the plot source, matching rules, and sample sizes.
- Volume, DBH, height, and stems are reported by species and age class where n permits.
- The decision is explicit: retain production curves or adopt a justified alternative.
- No curve or AAC change occurs without a separate ADR.
- Both instance dashboards and the ws4 docs build are green.

## Phase 49: Managed/young validation pre-registration

Parent issue: #335
Branch: `feature/p49-preregistration`
Status: complete

Goal: determine whether the public FAIB data contain an independent remeasured managed/young
sample large enough to test the Cw/Hw 16-80 gap, and pre-register the test before fitting any
correction.

- [x] P49.1 Inventory the candidate remeasured sample (#336)
- [x] P49.2 Write the pre-registered validation plan (#337)
- [x] P49.3 Decide data-limited or run, and close out (#338)

Acceptance:

- The inventory names candidate counts, fields, and gaps.
- The plan fixes the target population, exclusions, strata, metrics, and decision rule before results.
- The decision is explicit and does not tune to the AAC.
- No curve change occurs unless the pre-registered sample is met.
- Both instance dashboards and the ws4 docs build are green.

## Phase 50: Runtime provenance and release verification

Parent issue: #345
Branch: `feature/p50-runtime-provenance`
Status: complete

Goal: make the runtime matrices match the provenance published in P47-P49: refresh the sidecars
beside the current matrices, run `ws4 quality --check`, and publish the evidence.

- [x] P50.1 Refresh the runtime sidecars (#346)
- [x] P50.2 Run the quality gate and capture the reports (#347)
- [x] P50.3 Publish the runtime-provenance report and verify Pages (#348)

Acceptance:

- Both runtime matrices carry the current tracked sidecar.
- `ws4 quality --check` exits zero for both.
- The report names the matrix path, sidecar hash, quality status, and command.
- The instance docs link the report and both dashboards stay green.

## Phase 51: Release-candidate verification

Parent issue: #351
Branch: `feature/p51-release-candidate`
Status: complete

Goal: verify the current `main` as a release candidate without tagging or publishing: clean-checkout
install, full gates, package build, isolated wheel install, entry points, docs/Pages, and a
release-note/recommendation record.

- [x] P51.1 Run the clean-checkout install and full gates (#352)
- [x] P51.2 Build and install the artifacts and verify entry points (#353)
- [x] P51.3 Audit release metadata, docs/Pages, and write the recommendation (#354)

Acceptance:

- The clean-checkout test and dashboard pass.
- The sdist and wheel build and install in an isolated environment.
- `ws4` and `python -m ws4.cli` work from the installed wheel.
- Docs/Pages return 200 for the key pages.
- The report states whether the candidate is ready for a tag and names any blocker.
- No tag, release, version bump, or production-data change.

## Phase 52: Consume FEMIC-compiled LidarBC products

Parent issue: #317
Branch: `feature/p52-lidar-products`
Status: complete

Goal: pin and validate FEMIC LidarBC bundles, map terrain/canopy products to
fragment/block support, and preserve native-resolution provenance without
reimplementing discovery or materialization.

- [x] P52.1 Define the WS4 consumer contract for FEMIC LidarBC products (#318)
  - [x] Pin bundle id/version and per-product checksums
  - [x] Validate manifest, licence, CRS, resolution, vertical datum, and source tiles
  - [x] Add polygon support summaries without reprojection
  - [x] Validate shared slope/CHM parity with FHOPS
- [x] P52.2 Register and consume FEMIC-compiled LidarBC products (#319)
  - [x] Write the pin to the dataset manifest and sidecar
  - [x] Reference the bundle without copying or re-downloading tiles
  - [x] Add register/inspect/validate CLI and build integration
  - [x] Add missing/corrupt/incompatible failure tests
- [x] P52.3 Validate and map FEMIC native terrain products into WS4 (#320)
  - [x] Map slope/CHM to fragment support
  - [x] Map slope/CHM to dissolved block support
  - [x] Record bundle pin, checksums, CRS, resolution, and aggregation rules
  - [x] Add mapping fixtures and CRS/product failure tests
- [x] P52.4 Integrate FEMIC canopy and precision-forestry metrics into WS4 (#321)
  - [x] Map CHM height/cover/structure to fragment and block support
  - [x] Add optional VRI uncertainty comparison
  - [x] Add optional individual-tree summaries
  - [x] Record lineage, units, support, and caveats
  - [x] Add canopy/VRI/tree fixtures and CLI
- [x] P52.5 Integrate terrain/canopy fields into the WS4 compiled dataset (#322)
  - [x] Add optional prefixed LiDAR fields to fragment/block Parquet tables
  - [x] Record bundle pin, mapping hashes, fields, and support keys in the manifest
  - [x] Preserve validity for datasets without LiDAR fields
  - [x] Verify simulator loading with expanded fields
  - [x] Add `ws4 lidar integrate` and overwrite/failure tests
- [x] P52.6 Validate, benchmark, document, and close out P52 (#323)
  - [x] Run the end-to-end TFL 6 AOI validation
  - [x] Confirm WS4/FHOPS/FEMIC parity within 1e-9
  - [x] Record performance, storage, and OGL-BC evidence
  - [x] Add the close-out report and validation metrics

Acceptance:

- WS4 can validate and pin a FEMIC bundle.
- Polygon support summaries preserve the product CRS and native resolution.
- Shared-AOI slope/CHM values match FHOPS within the documented tolerance.
- No discovery or materialization is reimplemented in WS4.

## Phase 53: Version 0.2.0 release preparation

Parent issue: #371
Branch: `feature/p53-v020`
Status: complete

Goal: apply the approved 0.2.0 version, write the release notes, fix the license metadata warning,
and re-run the release gates without tagging.

- [x] P53.1 Bump the version and citation metadata (#372)
- [x] P53.2 Write the 0.2.0 release notes (#373)
- [x] P53.3 Fix license metadata, re-run the gates, and request tag approval (#374)

Acceptance:

- All version fields read 0.2.0.
- Release notes cover the changes since 0.1.0.
- The package builds without the license-classifier warning.
- Clean-checkout, dashboard, artifacts, isolated installs, entry points, and Pages pass.
- No tag or release is created.

## Phase 55: Final 0.2.0 release candidate

Parent issue: #388
Branch: `feature/p55-final-rc`
Status: complete

Goal: produce the final 0.2.0 release candidate after the carbon, LiDAR, hydrology, and
disturbance work landed, update the release notes, re-run the release gates on the final head,
and request tag approval.

- [x] P55.1 Update the 0.2.0 notes for P51/P52 and later merged phases (#389)
- [x] P55.2 Re-run the final release gates on the final head (#390)
- [x] P55.3 Request tag approval and close out (#391)

Acceptance:

- The notes match the final merged head and avoid claiming unfinished work.
- Known gaps list only still-open work.
- Clean-checkout, dashboard, artifacts, isolated installs, entry points, and Pages pass.
- No tag or release is created without explicit approval.

## Phase 56: Disturbance event consumer

Parent issue: #393
Branch: `feature/p56-disturbance-consumer`
Status: complete

Goal: consume `femic.disturbance.v1` consumer rows in a read-only report,
without changing the compiled dataset, simulator, or optimizer.

- [x] P56.1 Load and report disturbance events (#394)

Acceptance:

- The loader accepts the consumer-row shape and the full event record.
- The report names the event year, type, severity class, and affected blocks.
- A malformed event fails with a clear message.
- `ws4 disturbance --json` emits a stable summary.
- No compiled-dataset, simulator, or optimizer behavior changes.

## Phase 57: Consume FEMIC hydrology response bundles

Parent issue: #395
Branch: `feature/p57-hydrology-response`
Status: complete

Goal: consume pinned FEMIC hydrology response and flood-risk bundles for
screening-only spatial scheduling, without re-running FEMIC discovery,
frequency fitting, or surrogate training.

Closeout: pull request #411 squash-merged as `75399d3`; the phase report is
`notes/reports/p57-closeout.md`.

- [x] P57.1 Define and validate the FEMIC hydrology bundle consumer contract (#396)
  - [x] Add schema constants, immutable records, and a stable bundle pin.
  - [x] Implement load/validate with checksum, role, path, summary, and ID checks.
  - [x] Add `ws4 hydrology inspect|validate` and JSON error reporting.
  - [x] Add contract/failure tests and a synthetic fixture builder.
  - [x] Add the design note, reference docs, roadmap, and changelog entry.
- [x] P57.2 Register a pinned FEMIC hydrology bundle in a compiled dataset (#399)
  - [x] Add sidecar/registration helpers and bundle-reference resolution.
  - [x] Write and read `metadata.hydrology_products` and the sidecar.
  - [x] Revalidate a registered bundle against its pin.
  - [x] Add `ws4 hydrology register` and dataset `inspect|validate` modes.
  - [x] Add tests, design note, reference docs, roadmap, and changelog.
- [x] P57.3 Map WS4 support to FEMIC units, watersheds, and receptors (#401)
  - [x] Add crosswalk and metadata loaders with checksum and review-state records.
  - [x] Validate dataset/FEMIC IDs and derive fragment/block mappings safely.
  - [x] Write fragment/block CSVs and a deterministic mapping manifest.
  - [x] Add `ws4 hydrology map` and coverage/refusal reporting.
  - [x] Add tests, design note, reference docs, roadmap, and changelog.
- [x] P57.4 Screen a schedule against FEMIC flood-risk response and risk rows (#403)
  - [x] Add mapping/schedule loaders and a typed screening result.
  - [x] Derive watershed harvest fractions and scenario applicability checks.
  - [x] Join response ratios and flood-risk rows; refuse outside tolerance.
  - [x] Add CSV/JSON writers and `ws4 hydrology screen`.
  - [x] Add tests, design note, reference docs, roadmap, and changelog.
- [x] P57.5 Price optional flood-risk accounts in the optimizer (#407)
  - [x] Add the flood-screen config and `FloodRiskModel`.
  - [x] Append `flood.*` rows and price normal targets on them.
  - [x] Refuse out-of-envelope schedules with the configured penalty.
  - [x] Add `--flood-screen-config` to optimize/watch/calibrate.
  - [x] Add tests, design note, reference docs, roadmap, and changelog.
- [x] P57.6 Validate, document, and close out the hydrology consumer phase (#410)
  - [x] Run the full hydrology contract suite and dashboard.
  - [x] Record end-to-end evidence and limitations.
  - [x] Write the close-out report and set P57 status to `pr-open`.
  - [x] Update changelog and post closeout comments.
  - [x] Queue the stacked PRs for maintainer approval.

Acceptance:

- A valid bundle returns a stable pin and per-artifact SHA-256/size records.
- Tampered, missing, path-escaping, wrong-schema, missing-role, and ID-mismatch
  bundles fail with specific errors.
- CLI JSON reports are deterministic and exit non-zero on invalid input.
- Validation is stdlib-only and never contacts FEMIC or the network.
- The screening-only and hydrologist-review conditions remain explicit.

## Phase 58: Forest carbon accounting and carbon-aware planning

Parent issue: #357
Branch: `feature/p58-carbon`
Status: complete

Goal: make carbon a first-class, reproducible outcome of a WS4 run and a target the optimizer can
search against, using libcbm as the engine and FEMIC as the producer of the carbon input package.

Architecture: the compiled dataset remains the runtime contract. `ws4 carbon` reads it plus a FEMIC
carbon package and a schedule, compiles CBM SIT tables, and runs libcbm behind a small driver
protocol. Carbon outputs are `carbon.*` accounts. The optimizer sees carbon through a block-level
ledger that reuses CBM's stand-level additivity, or through a clearly labeled surrogate when the
ledger cannot meet the search budget. The final schedule is always verified with the exact engine.
See `notes/design/ws4-carbon.md`.

- [x] P58.1 Load and validate FEMIC carbon packages (#358)
- [x] P58.2 Compile CBM SIT tables from a WS4 dataset and schedule (#359)
- [x] P58.3 Add the libcbm driver and the `ws4 carbon` command (#360)
- [x] P58.4 Integrate carbon accounts, reports, and provenance (#361)
- [x] P58.5 Validate parity, mass balance, and deterministic replay (#362)
- [x] P58.6 Build the block-level carbon ledger (#363)
- [x] P58.7 Add carbon targets to the optimizer (#364)
- [x] P58.8 Validate carbon-aware planning on TSA24 and MKRF (#365)
- [x] P58.9 Consume GCBM outputs and compare spatial carbon (#366)
- [x] P58.10 Document, release, and close out the carbon phase (#367)

Acceptance:

- `ws4 carbon` runs on a real compiled dataset and schedule and writes pools, fluxes, accounts, and a
  manifest.
- The same inputs replay identically, and the manifest records the package, schedule, libcbm, and
  `cbm_defaults` hashes.
- WS4 and WS3 agree within a documented tolerance on the TSA24 fixture, or the difference is explained.
- A carbon target changes a schedule on a small instance, and the winning schedule is verified with the
  exact engine.
- TSA24 and MKRF carbon-aware runs are recorded with their trade-offs and runtimes.
- GCBM outputs can be ingested and compared without making FLINT a WS4 runtime dependency.

Closeout report: `notes/reports/p58-closeout.md`.

## Phase 59: LiDAR in the web UI

Parent issue: #417
Branch: `feature/p59-lidar-ui`
Status: complete

Goal: expose registered FEMIC LiDAR provenance, canonical block fields, block detail, and a
read-only block choropleth in the web application, and repair the P52 overwrite path.

- [x] P59.1 Add the LiDAR API and canonical field contract (#418)
  - [x] Add the API and field-label helper
  - [x] Join fields into the map response when requested
  - [x] Repair overwrite and add the duplicate-column regression test
- [x] P59.2 Add the LiDAR panel, map coloring, and block details (#419)
  - [x] Add the tab, provenance card, and unavailable state
  - [x] Add the field selector, scale, and legend
  - [x] Add block-detail values and reset behavior
- [x] P59.3 Verify real data, document, and close out (#420)
  - [x] Regenerate the TFL 6 validation dataset without duplicate columns
  - [x] Run the browser/API smoke
  - [x] Verify the c5 fallback and write the close-out

Acceptance:

- A registered dataset shows bundle pin, CRS, licence, products, and fields.
- A dataset without LiDAR shows an explicit unavailable state.
- Selected fields colour blocks and appear in the block detail.
- Overwrite leaves one canonical column per field.
- The TFL 6 validation dataset and c5 fallback are both exercised.
- `python scripts/dashboard.py` is green.

## Phase 60: Harden hydrology use with validation evidence

Parent issue: #415
Branch: `feature/p60-closeout`
Status: complete

Goal: read FEMIC validation-report and model-card evidence, report review and
tail-check state, and prepare an explicit policy for provisional use.

Closeout: pull request #428 squash-merged as `b2012bd`; the phase report is
`notes/reports/p60-closeout.md`. It was renumbered from P59 after the LiDAR UI
PR claimed P59.

- [x] P60.1 Read and report FEMIC validation and model-card evidence (#416)
  - [x] Add evidence dataclasses and readiness assessment.
  - [x] Parse validation-report and model-card artifacts with schema checks.
  - [x] Add `ws4 hydrology readiness` direct/dataset modes.
  - [x] Add tests and fixture variants.
  - [x] Add design note, reference docs, roadmap, and changelog.
- [x] P60.2 Gate hydrology screening and optimization on readiness evidence (#423)
  - [x] Add readiness policy constants and enforcement helper.
  - [x] Extend screen CLI and flood-screen config.
  - [x] Enforce readiness at `FloodRiskModel` construction.
  - [x] Add tests for policy/status, CLI, and optimizer refusal.
  - [x] Add design note, reference docs, roadmap, and changelog.
- [x] P60.3 Validate, document, and close out P60 (#426)
  - [x] Run the hydrology contract suite and dashboard.
  - [x] Record the P59 collision and renumbering.
  - [x] Write the close-out report and set P60 to `pr-open`.
  - [x] Update changelog and post closeout comments.
  - [x] Queue the single phase PR for maintainer approval.

Acceptance:

- Missing evidence is reported as `not_available`, not approved.
- Provisional evidence is reported explicitly.
- Tail-check failures are surfaced as blocking evidence.
- A reviewed, clean card is reported as ready.
- No screen/optimizer behavior changes in P60.1.

## Phase 61: Carbon and libcbm in the web UI

Parent issue: #430
Branch: `feature/p61-carbon-ui`
Status: complete

Goal: expose the P58 carbon artifacts in the web application without re-running libcbm.

- [x] P61.1 Add carbon run discovery and the carbon API (#431)
  - [x] Add carbon-only discovery and period/account fallbacks
  - [x] Add the carbon endpoint and timestep aggregation
  - [x] Add artifact, empty-state, and carbon-only tests
- [x] P61.2 Add the Carbon panel and charts (#432)
  - [x] Add the tab, provenance, and unavailable state
  - [x] Add the account selector, trend, and composition bars
  - [x] Add ledger, comparison, downloads, and reset
- [x] P61.3 Verify real TSA24/MKRF data and close out (#433)
  - [x] Add the carbon browser smoke
  - [x] Verify TSA24/MKRF API/UI evidence
  - [x] Verify the non-carbon fallback and write the close-out

Acceptance:

- Carbon provenance, accounts, pools, ledger, and comparison are readable.
- Carbon accounts match the CSV values.
- Browser smoke passes on real TSA24 data and the non-carbon state is explicit.
- `python scripts/dashboard.py` is green.

## Phase 62: Harden the hydrology consumer and explicit road/culvert exposure

Parent issue: #437
Branch: `feature/p62-hydrology-consumer`
Status: active

Goal: make the WS4 hydrology consumer fail closed when evidence is incomplete,
and add an explicit road/culvert exposure input by watershed and period. This is
a consumer-hardening phase, not a watershed flood pilot. Chapman is closed as
data-blocked in FEMIC #383; Seymour depends on FEMIC #388 and has no reviewed
bundle yet.

Design note: `notes/design/ws4-hydrology-consumer-hardening.md`.

- [x] P62.1 Re-scope P62 and record the consumer boundary (#449)
  - [x] Rewrite the parent issue and add the phase to the roadmap.
  - [x] Write the design note and index it.
  - [x] Add the changelog entry and read back every GitHub edit.
- [x] P62.2 Add a fail-closed hydrology preflight report (#450)
  - [x] Add the preflight report and CLI command.
  - [x] Block invalid bundles, blocked readiness, weak policy, unreviewed crosswalks, and incomplete mapping.
  - [x] Add tests and reference docs.
- [ ] P62.3 Add an explicit road/culvert exposure contract (#451)
  - [ ] Add the exposure schema, loader, and validation.
  - [ ] Bind the table to a schedule hash and require review metadata.
  - [ ] Add fixtures, tests, and reference docs.
- [ ] P62.4 Use exposure in screening and guard the optimizer (#452)
  - [ ] Add exposure features to one-schedule screening.
  - [ ] Record exposure identity, schedule hash, and refusals.
  - [ ] Refuse fixed exposure in the optimizer and add tests/docs.
- [ ] P62.5 Prove the consumer path on a synthetic fixture (#453)
  - [ ] Add the end-to-end fixture and success path.
  - [ ] Add the fail-closed matrix.
  - [ ] Update the docs and design note.
- [ ] P62.6 Validate, document, and close out P62 (#454)
  - [ ] Run the suites and dashboard.
  - [ ] Write the closeout report and update the roadmap/changelog.
  - [ ] Queue the single phase PR for approval.

Acceptance:

- `hydrology preflight` cannot report ready when a required condition fails.
- Exposure is explicit, reviewed, schedule-bound, and never inferred.
- Screening records exposure identity and schedule hash.
- The optimizer refuses fixed exposure instead of reusing it across candidates.
- The synthetic path covers success and fail-closed cases.
- The closeout states that no real watershed or flood result exists.

## Detailed Next Steps Notes

1. Phase 0 is complete: pull request #8 squash-merged as `97330a8`, the branch deleted, and parent
   issue #1 closed. The close-out report is `notes/reports/p0-closeout.md`.
2. Phase 1 is complete: pull request #14 squash-merged as `a3d182a`, the branch deleted, and parent
   issue #10 closed. The close-out report is `notes/reports/p1-closeout.md`.
3. Phase 2 is complete: pull request #25 squash-merged as `27b6915`, the branch deleted, and parent
   issue #15 closed. The close-out report is `notes/reports/p2-closeout.md`. Five items are deferred and
   listed in the Phase 2 section and tracked in `notes/backlog.md`.
4. P2 builds the model and the optimization stack. The stack generalizes the lab's FHOPS toolkit into a
   shared solver core; the execution substrate targets the 72-core host and the GPU. See
   `notes/design/ws4-optimization-stack.md` and `notes/design/ws4-matrix-builder-and-interop.md`.
5. Phase 3 is complete: pull request #35 squash-merged as `a8dc018`, the branch deleted, and parent
   issue #26 closed. The close-out report is `notes/reports/p3-closeout.md`, and the verification report
   is `notes/reports/p3-verify.md`.
6. Phase 4 is complete: pull request #43 squash-merged as `d8ecd72`, the branch deleted, and parent
   issue #36 closed. The annotated tag `v0.1.0` was created and pushed, and the GitHub release
   `v0.1.0` published the sdist and the wheel. The docs site and the published artifact were verified
   (P4.4, P4.6). The close-out report is `notes/reports/p4-closeout.md`.
7. Performance is the next major effort, **after** the phase 4 initial release. The release is
   functionally complete but slow on space-and-roads workloads (routing, patch accounts, edge contrast,
   and core area run inside the optimizer objective). The plan — profiling, bottleneck map, targets, and
   the ordered work packages — is `notes/design/ws4-performance.md`. The implementation is deliberately
   deferred: no optimization work lands before the release merges.
8. Phase 5 is complete: pull request #51 squash-merged as `a8cb148`, the branch deleted, and parent
   issue #44 closed. The close-out report is `notes/reports/p5-closeout.md`.
9. Phase 6 (Performance and scalability) is active on `feature/p6-performance`, parent issue #60, with
   eight work packages (#61 to #68) from the plan in `notes/design/ws4-performance.md`: the benchmark
   harness and baseline, route and simulation quick wins, a vectorized simulator core, spatial
   precompute and incremental metrics, incremental objective evaluation, solvers at scale, native
   kernels, and the guardrails.

10. Phase 6 is complete: pull request #81 squash-merged as `f5d6f27`, the branch deleted, and parent
    issue #60 closed. The close-out report is `notes/reports/p6-closeout.md`, and its acceptance
    evidence is the C5 benchmark, the incremental move cost, and the island scaling recorded there.
    Phase 7 (Parity and the analyst workflow) is active on `feature/p7-parity`, parent issue #82, with
    five tasks (#83 to #87): the command-line gaps, the `threads` setting and a scaling re-measurement,
    a sample estate, the missing notebooks and a concepts section, and patch performance under a dense
    harvest.

11. Phase 7 is complete: pull request #89 squash-merged as `1dc2c97`, the branch deleted, and parent
    issue #82 closed. The close-out report is `notes/reports/p7-closeout.md`. Its most valuable result
    was not a feature: shipping the sample estate exposed that `Optimizer.run` replayed its incumbent
    without passing the patch accounts, so a patch target was reported as a zero share carrying its
    whole penalty while the summary's own objective was zero — the search had been right. Phase 8
    (Verify the replacement claim) is active on `feature/p8-verify`, parent issue #90, with four tasks
    (#91 to #94): a parity harness against the reference outputs, the C5 results reproduced from
    documented inputs, the criterion-series and patch-state performance lever P7.5 named, and island
    scaling on a host whose load is recorded.

12. Phase 8 is complete: pull request #96 squash-merged as `e8b5248`, the branch deleted, and parent
    issue #90 closed. The close-out report is `notes/reports/p8-closeout.md`, and its acceptance
    evidence is the routing parity comparison (no differences in 37,701 comparisons against the
    reference's own per-node haul costs), the C5 figures reproduced from documented commands, the
    criterion series made 29% cheaper, and island scaling re-measured at a recorded load with its cause
    measured as the memory hierarchy. **#95 was deferred to Phase 9** rather than holding the phase open
    on an export from a licensed Windows run, and is renumbered P9.5 as a sub-issue of the new parent.
    Phase 9 (Spatial performance and memory) is active on `feature/p9-memory`, parent issue #97, with
    five tasks (#98 to #101 and #95).

13. Phase 9 is active on `feature/p9-memory`, parent issue #97: #98 to #101 are complete, #102 (the
    type gate) landed while #95 waits on the Windows export, and **#103 (growth parity against the
    reference's own yields) is next** — the reference ships its yield table, so growth can be checked
    without a licensed machine, and it narrows what the accounts comparison can mean.

    Requested while waiting, in order, after #103: **an API-first notebook** (all seven examples are
    CLI-first, so the programmatic audience is not yet first-class in the examples gallery), and then
    **capability work from the backlog's `partial` items** (succession and `produce` semantics,
    legacy-ingestion coverage, account reports). Both are outside this phase's subject — spatial
    performance and memory — so they are recorded here as planned and are launched as their own phase
    rather than folded into P9.

14. Phase 9 is **held open only for P9.5**: every other task in it is complete and closed (#98-#103),
    and #95 waits on an export from a licensed Windows run of the reference. Rather than leave the
    waiting time unused, and rather than widen P9's subject, the requested documentation work is its own
    phase: **P10 (Documentation and the API-first workflow)**, parent issue #104, branch
    `feature/p10-docs-api`, tasks #105-#107. The remaining backlog capability work — succession and
    `produce` semantics, legacy-ingestion coverage, account reports — is the phase recorded after it.

15. Phase 10 is complete: pull request #109 squash-merged as `b512cd9`, the branch deleted, and parent
    issue #104 closed. It delivered the library-path notebook the gallery was missing, a check that
    re-runs every example and reports output that has drifted from what is committed (its first three CI
    runs each found a real defect), path labels on every example, and the fix for a report that priced a
    periodic target from a single year — found by writing the notebook. Its pull request was stacked on
    `feature/p9-memory` and merged there, because Phase 9 branched it and Phase 9's own close-out has not
    run yet; the two phases now reach `main` together. Phase 9's remaining work is closed except its
    close-out, and the next phase is the derived targets the accounts comparison leaves out — the
    reference's ratios, flow constraints and patch-size distributions.

16. Phase 9 is complete: pull request #111 squash-merged as `e48c308`, the branch deleted, and parent
    issue #97 closed. It landed with Phase 10, which had been stacked on its branch and merged into it
    (`b512cd9`) — the two phases reached `main` together, as approved. Its close-out report is
    `notes/reports/p9-closeout.md`; its acceptance evidence is the shared-dataset attempt measured and
    reverted, island scaling reproducing P8.4 at a recorded load, the patch-state construction 89%
    cheaper and the curve gather 24% cheaper, the type gate widened to the package, and **the accounts
    comparison passing on both 2026 scenarios — 1,323 account-period values each** — which is also what
    found the matrix-builder defect that had been mis-attributing every managed and unmanaged account
    since the 2019 sample. Phase 11 (The derived targets and the sample's own files) is active on
    `feature/p11-derived-targets`, parent issue #112, with six tasks (#113 to #118).

17. Phase 11 is complete: pull request #119 squash-merged as `0d34412`, the branch deleted, and parent
    issue #112 closed. Its close-out report is `notes/reports/p11-closeout.md`; its acceptance evidence is
    the period convention matched to the reference's (products were 24% low and features ten times high
    before it), the flow constraints negotiated and their reporting bug closed, **routing parity on all
    25,134 node-and-mill pairs** of the 2026 sample, a patch family compared over 630 cells across six
    quantities, 959 yield-curve points reproduced from either vintage's shape, and two WS4 defects fixed
    along the way — the matrix builder's track attribution and road maintenance charged per routed flow
    rather than once per used road. Three capabilities it could not reach are named with measurements and
    are the substance of Phase 12 (**Spatial decision match**), active on
    `feature/p12-spatial-decisions`, parent issue #120, with six tasks (#121 to #126).

18. Phase 12 is complete: pull request #127 squash-merged as `35e96a9`, the branch deleted, and parent
    issue #120 closed. Its close-out report is `notes/reports/p12-closeout.md`; its acceptance evidence is
    the destination decisions compared block-period by block-period for the first time (the reference's
    splits read from its own model, deciduous matching to **4 units in 2.78 million** and conifer to
    **91.7%** of block-periods), the route report folded into the model's periods and written per
    destination, `period_width` wired through at last, and a parity mode that names its one deliberate
    divergence and measures it (**+4.2%**, **+42.4%** and **×5.24** of parity). Four things were refused
    or limited with the measurement that says why — a product patch criterion whose values land ten years
    late, the attractor, the patch components, and the single route-report column `LENGTH` — and two more
    WS4 defects were found on the way: **27 products were being routed to the mills as wood**, and road
    maintenance was charged 7.0× in the route accounts of what the report charged. The deferred items are
    triaged in `notes/backlog.md` and are the subject of Phase 13.
19. Phase 15 is complete: pull request #139 squash-merged as `f22a026`, the branch deleted, and parent
    issue #138 closed. Its close-out report is `notes/reports/p15-closeout.md`. The acceptance evidence
    is the synthetic oracle (a full-span band cuts the 490 ha lattice to 210 ha, a partial band leaves
    450 ha, and the patch account cannot rank the two full bands) and the TSA23 bridge instance, where
    the **compartment** reading reproduced the fire ranking — largest 82,800 / 104,600 / 187,173 ha and
    area-weighted mean 25,675 / 31,604 / 46,419 ha against 19,640 / 19,870 / 20,298 ha burned — after
    the phase's first, **directed** definition was measured to read a boundary corridor (3,390.6 ha
    identical for all three patterns) and to reverse the mean. The account is wired into a run and the
    optimizer and documented in `docs/reference/spatial.rst`. Four limits are recorded rather than
    claimed: the bridge treats 177,088 ha of whole blocks against WS4's ~46,600 ha of managed fragments;
    the fire spread is 3% on one seed; the ordering holds from a 60° to a 90° cone and flips at 45°; and
    the FT product's curve still reads 4.0. Those are the subject of the proposed P16 (the bridge at the
    same footprint, the load-time 4× check, and the account's final shape).
20. Phase 14 is complete: pull requests #135 (`809cc1d`) and #137 (`cc37fde`) merged, and parent issue
    #133 closed. Its close-out report is `notes/reports/p14-closeout.md`. The criteria that the phase
    had deferred are now measured on the TSA23 instance: with `--seed-greedy` the run reaches **penalty
    0.00** at **$199,999,193** against the $200,000,000 ceiling (9,999.96 ha treated), where unseeded it
    stops at **15,758.97**; the corrected five-year targets, both bounds on the cost account, reach
    **0.00** as well. Both seeded runs report `time_limit_reached: false`, so the budget did not cut
    them. The v1 floor is read through a dataset curve that reports 4× the treated hectares; that is a
    compile defect, recorded in the report and left to P16.2's load-time guard.
21. Phase 16 is complete: pull request #142 (`P16.2`) merged as `8f0f6d4`, the documentation pull request
    that carries this note and the reports merged, and parent issue #141 closed. The matched-footprint
    rerun (P16.1) is a **negative** result: at the ~54,000 ha WS4 can treat, the fire model's ranking is
    not stable across five seeds (mean order clumped < random < barrier, the reverse of the published
    order, with a 0.38% gap against a 15% seed range), so the P15 bridge validation is withdrawn and
    the account stands as a fragmentation metric, not a fire-response proxy. P16.2 fixed the real 4×
    cause — 1,515,465 exact duplicate product rows, not a 4.0 curve — in the builder and in the loader
    warning. Reports: `notes/reports/p16-bridge-matched.md` and `notes/reports/p16-closeout.md`.
22. Phase 13 is complete: parent issue #128 closed. P13.1 and P13.2 were merged earlier (#130, #132);
    the two items that remained — what the route report's `LENGTH` counts and its distance unit — were
    resolved by P17: `LENGTH` is the **distinct road used in the period, counted once**, and
    `AVERAGEHAULDIST` is reported in kilometres, the reference's unit. Patch membership and the
    reference's per-segment road construction remain named as unverifiable/not required. Report:
    `notes/reports/p13-closeout.md`.
23. Phase 17 is complete: parent issue #145 closed. Pull requests #147 (opened roads), #148 (period
    `LENGTH`), #149 (period maintenance) and the report pull request merged. The accounting definitions
    now match the reference — `LENGTH` 0.77×, maintenance 0.93×, volume 1.00× — after two period-quantity
    defects were found and fixed (annual distinct lengths summed; maintenance charged per year). The
    remaining difference is a **model-objective** one, named: the reference builds 1.9× more road at the
    same cost per metre and hauls 22% farther at 0.46× the cost per unit-km, because its solve chooses
    the road set and the assignment jointly. Reports: `p17-opened-roads.md`, `p17-tradeoff.md`,
    `p17-closeout.md`. Next: P18.
