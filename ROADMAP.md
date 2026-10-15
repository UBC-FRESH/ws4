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
| P3 Verify | #26 | `feature/p3-verify` | pr-open |
| P4 Release and deploy | TBD | `feature/p4-release` | planned |
| P5 Operate and maintain | TBD | `feature/p5-operate` | planned |

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
  - [x] ForestModelXML parser and structural validation (parses the real MKRf recipe: 1057 curves, 11 selects, 2 treatments)
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
- blocked: the full MKRf canonical model (needs its generated XML).

## Phase 3: Verify

Parent issue: #26
Branch: `feature/p3-verify`
Status: pr-open

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

Parent issue: TBD
Branch: `feature/p4-release`
Status: planned

Goal: tag a release, publish the artifacts and the docs, and verify the published release from a clean
checkout.

- [ ] P4.1 Prepare the release: version, changelog, license, citation, and packaging metadata
- [ ] P4.2 Write the release notes and the known-gaps list
- [ ] P4.3 Build and verify the release artifacts (sdist and wheel) from a clean checkout
- [ ] P4.4 Publish the documentation site and verify it from a clean checkout
- [ ] P4.5 Tag the release and publish the artifacts (maintainer approval required)
- [ ] P4.6 Verify the published release: install it fresh, run the acceptance checks, and confirm
      reproducibility

## Phase 5: Operate and maintain

Parent issue: TBD
Branch: `feature/p5-operate`
Status: planned

Goal: keep the project current: triage incoming ideas, review on a cadence, and close out cleanly.

- [ ] P5.1 Set a review cadence and record the first review
- [ ] P5.2 Stand up issue triage: labels, templates, and a triage cadence
- [ ] P5.3 Dependency and security maintenance: automated updates and a review cadence
- [ ] P5.4 Keep the roadmap, backlog, and changelog in step on a cadence
- [ ] P5.5 Define the release cadence and the patch policy
- [ ] P5.6 Write the maintainer and handover guide

## Detailed Next Steps Notes

1. Phase 0 is complete: pull request #8 squash-merged as `386c643`, the branch deleted, and parent
   issue #1 closed. The close-out report is `notes/reports/p0-closeout.md`.
2. Phase 1 is complete: pull request #14 squash-merged as `33ac569`, the branch deleted, and parent
   issue #10 closed. The close-out report is `notes/reports/p1-closeout.md`.
3. Phase 2 is complete: pull request #25 squash-merged as `3e87d46`, the branch deleted, and parent
   issue #15 closed. The close-out report is `notes/reports/p2-closeout.md`. Five items are deferred and
   listed in the Phase 2 section and tracked in `notes/backlog.md`.
4. P2 builds the model and the optimization stack. The stack generalizes the lab's FHOPS toolkit into a
   shared solver core; the execution substrate targets the 72-core host and the GPU. See
   `notes/design/ws4-optimization-stack.md` and `notes/design/ws4-matrix-builder-and-interop.md`.
5. Phase 3 is queued for close-out on `feature/p3-verify`, parent issue #26, with eight tasks (#27 to
   #34): the acceptance checks, determinism and reproducibility, correctness (regression and
   invariants), the spatial constraints, scale and performance, packaging and docs from a clean
   checkout, the deferred-item triage and verification report, and the spatial-constraint enforcement.
   The pull request is open and the report is `notes/reports/p3-closeout.md`; the verification report is
   `notes/reports/p3-verify.md`.
