# Maintainer and handover guide (P5.6)

This guide orients a new maintainer: the repository layout, the workflow, the gates, and the release
steps.

## What WS4 is

A CLI-first, HPC-ready forest estate model: fragments are the decision units, blocks aggregate them at
runtime, and adjacency, patch structure, and road access participate in simulation and optimization.
The compiled matrix dataset is the runtime contract. See `AGENTS.md`, `ROADMAP.md`, and
`notes/design/ws4-architecture.md`.

## Repository map

- `ws4/` — the package: `build/` (matrix builder, ingestion), `io/` (recipe parser, expressions,
  fragments), `sim/` (simulator, curves), `opt/` (objective, operators, solvers, MIP, telemetry),
  `patch/` (metrics, constraints, patch accounts, edge contrast), `roads/` (network, route accounts),
  `model/` (schema, API), `report.py`, `cli.py`.
- `scripts/` — `dashboard.py` (all gates), `check_workflow.py` (the validator), `acceptance.py`,
  `benchmark.py`.
- `docs/` — the Sphinx site (`reference/` pages, `api/`, `llms.txt`).
- `notes/` — the working notes: `backlog.md`, `performance.md`, `review-cadence.md`, `triage.md`,
  `dependencies.md`, `release-policy.md`, `sync-checklist.md`, `handover.md`; `adr/`, `design/`,
  `reports/`.
- `.github/` — CI and docs workflows, issue templates, the pull request template, Dependabot.

## Workflow in one page

- One phase is one parent issue, one branch (`feature/p<n>-<slug>`), and child task issues.
- One task is one child issue (a sub-issue of the parent), with subtasks as a checklist.
- A phase ends with a close-out report in `notes/reports/`, a pull request into `main`, and maintainer
  approval; the report names every tag, release, or settings change with its exact command.
- One bounded move at a time; stop and report after each.

## Gates

`python scripts/dashboard.py` runs lint, format, strict types, tests with a 90 percent coverage gate,
the workflow validator, and the docs build (warnings as errors). It must be `OVERALL: GREEN` at every
commit. CI runs the same gates on pull requests and on `main`.

## Releases

Follow `notes/release-policy.md`. In short: bump the version, merge, tag `vX.Y.Z`, publish the GitHub
release with the sdist and wheel built from a clean checkout of the tag, and verify a fresh install.
The `Docs` workflow deploys the site from `main`.

## Environment

- Python 3.11+; `pip install -e ".[geo]"` adds the shapefile reader, `.[opt]` adds the solver extras.
- The reference sample model (C5) is unpacked outside the repository; nothing from it is committed.
- The 72-core host is the target for the parallel and GPU execution work.

## Where the next effort is

Performance and scalability: the plan (profiling, bottleneck map, targets, and ordered work packages)
is `notes/design/ws4-performance.md`. The released version is functionally complete but slow on
space-and-roads models; this plan is the next build phase after P5.
