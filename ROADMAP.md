# WS4 Roadmap

This roadmap is the plan of record and the issue tracker map for WS4. Keep it in step with the GitHub
issues, `CHANGE_LOG.md`, and `notes/`. `scripts/check_workflow.py` parses the phase headers, status
lines, and checkboxes below, so keep their format.

Every phase starts as `planned` with `Parent issue: TBD`. Activate a phase only after its parent issue
exists and the maintainer approves it.

## Issue Tracker Map

| Phase | Parent issue | Branch | Status |
| --- | --- | --- | --- |
| P0 Scope and design | #1 | `feature/p0-scope-design` | pr-open |
| P1 Contracts and prototype | TBD | `feature/p1-contracts-prototype` | planned |
| P2 Build | TBD | `feature/p2-build` | planned |
| P3 Verify | TBD | `feature/p3-verify` | planned |
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
Status: pr-open

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

Parent issue: TBD
Branch: `feature/p1-contracts-prototype`
Status: planned

Goal: fix the data contracts and build the smallest end-to-end prototype that exercises them on
synthetic data.

- [ ] P1.1 Define the compiled-dataset schema and manifest in `docs/`
- [ ] P1.2 Build a prototype that compiles, simulates, and reports on a tiny synthetic landscape

## Phase 2: Build

Parent issue: TBD
Branch: `feature/p2-build`
Status: planned

Goal: implement the agreed scope, one task at a time, on the phase branch.

- [ ] P2.1 Implement the ingestion and compilation pipeline
- [ ] P2.2 Implement the simulation engine
- [ ] P2.3 Implement the optimization engine: objective, operators, and one metaheuristic
- [ ] P2.4 Implement the solver core: the shared operator/metaheuristic/tuning/telemetry package
- [ ] P2.5 Implement the parallel and GPU execution substrate (process pool, islands, tensorized moves)
- [ ] P2.6 Implement the math-heuristic layer (MIP bounds, warm starts, destroy-repair)
- [ ] P2.7 Implement the spatial and road subsystems
- [ ] P2.8 Implement accounts and reporting

## Phase 3: Verify

Parent issue: TBD
Branch: `feature/p3-verify`
Status: planned

Goal: show that the build meets its acceptance criteria, and record the evidence in the changelog.

- [ ] P3.1 Run the acceptance checks and record the evidence

## Phase 4: Release and deploy

Parent issue: TBD
Branch: `feature/p4-release`
Status: planned

Goal: tag a release, publish the docs, and verify the published artifacts from a clean checkout.

- [ ] P4.1 Write the release notes and the known-gaps list
- [ ] P4.2 Tag, publish, and verify from a clean checkout (maintainer approval required)

## Phase 5: Operate and maintain

Parent issue: TBD
Branch: `feature/p5-operate`
Status: planned

Goal: keep the project current: triage incoming ideas, review on a cadence, and close out cleanly.

- [ ] P5.1 Set a review cadence and record the first review

## Detailed Next Steps Notes

1. Phase 0 is `pr-open` on `feature/p0-scope-design`. The scope, ADRs, architecture note, and workflow
   tooling are complete. Pull request #8 and the close-out report `notes/reports/p0-closeout.md` await
   the maintainer's approval.
2. On approval: squash-merge #8, delete the branch, close parent issue #1, and launch P1 (contracts and
   prototype) with branch `feature/p1-contracts-prototype`.
3. P1 fixes the compiled-dataset schema and builds the smallest end-to-end prototype on synthetic data.
4. P2 builds the model and the optimization stack. The stack generalizes the lab's FHOPS toolkit into a
   shared solver core; the execution substrate targets the 72-core host and the GPU. See
   `notes/design/ws4-optimization-stack.md`.
