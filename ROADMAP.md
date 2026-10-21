
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
  the access network. P19.1 and P19.2 now add the model spread-compartment membership and the run's
  used-road overlay; the MapLibre swap waits for a basemap need.
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
