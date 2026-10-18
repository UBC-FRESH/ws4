
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
| P9 Spatial performance and memory | #97 | `feature/p9-memory` | active |
| P10 Documentation and the API-first workflow | #104 | `feature/p10-docs-api` | pr-open |

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
Status: active

Goal: act on what Phase 8 measured. P8.4 established that island scaling stops being near-linear because
of the memory hierarchy — not BLAS, not the per-process setup, not SMT, each excluded by measurement —
and found the concrete reason a shared dataset would not help as things stand: every process loads its
own copy before doing anything, and the simulator writes to the fragments frame it inherits.

- [x] P9.1 Share the dataset across worker processes (#98)
- [x] P9.2 Re-measure island scaling with the dataset shared (#99) — measured and rejected; #98 reverted
- [x] P9.3 Make the patch-state construction cheaper (#100) — the group topology is shared across years
- [x] P9.4 Stop rebuilding bounds in every curve gather (#101)
- [ ] P9.5 Compare WS4's accounts against a reference report (#95, carried from P8)
- [x] P9.6 Put the package under the type gate (#102) — the gate checked 50 files, it now checks 93
- [x] P9.7 Check growth against the reference's own yields (#103) — 959 yield-curve points reproduced; one conflict in the sample's own files, recorded

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
Status: pr-open
Pull request: stacked on `feature/p9-memory`, because Phase 9 is held open for its P9.5 export and
Phase 10 was branched from it. The stack lands as P9 then P10 unless the maintainer prefers one merge.

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

