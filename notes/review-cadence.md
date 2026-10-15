# Review cadence (P5.1)

The project is reviewed on a cadence so the roadmap, the backlog, and the changelog stay in step and
regressions or drift are caught early.

## Cadence

- **Monthly**, on the first working day of the month. The reviewer is the maintainer (a rotating
  deputy for cover).
- **Out-of-cadence triggers:** a security advisory that affects a dependency; a broken release or a
  red `main`; a new external input (a dataset, a model, or a collaborator) that changes scope.

## Review scope

1. `ROADMAP.md` — the active phase, its task boxes, and the issue map.
2. `notes/backlog.md` — new gaps, closed gaps, and the target phase for each.
3. `CHANGE_LOG.md` — that it is current and matches the merged work.
4. Open issues and pull requests — stale items, labels, and priority.
5. `notes/performance.md` — that the recorded figures still hold.

`python scripts/dashboard.py` must be green at the start and end of the review.

## First review (2026-10-15)

- **Releases.** P4 released `v0.1.0` (squash merge `a06d0ca`); the artifacts install and run from a
  fresh environment. See `notes/reports/p4-closeout.md`.
- **Roadmap/backlog.** The MKRF canonical model, the C5 route model and patch accounts, and the
  spatial gaps (core-area rules and edge contrast) are done. The performance and scalability work is
  deferred with a plan (`notes/design/ws4-performance.md`) and is the next build phase.
- **Open items.** The post-release backlog items are tracked with target phases; nothing is
  release-blocking. The producer's git-annex location log for the MKRF artifacts is still not on
  `origin` (the objects are on `arbutus-s3`).
- **State.** `main` is `9e4419d`; the dashboard is green; the docs site and the `v0.1.0` release are
  published. Phase 5 (Operate and maintain) is active on `feature/p5-operate`, parent issue #44.
- **Actions.** Stand up issue triage (P5.2), dependency maintenance (P5.3), a roadmap/backlog/changelog
  sync checklist (P5.4), a release and patch policy (P5.5), and a maintainer and handover guide (P5.6).
  Plan the performance build phase to follow P5.
