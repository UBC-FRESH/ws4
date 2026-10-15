# Roadmap, backlog, and changelog sync (P5.4)

The three planning documents must tell the same story. `scripts/check_workflow.py` enforces the
machine-checkable parts (phase headers, statuses, task boxes, links); this checklist covers the
judgment parts. The sync runs at the review cadence (`notes/review-cadence.md`).

## Checklist

- [ ] Every phase in `ROADMAP.md` has a parent issue, a branch, and a status consistent with
      `notes/review-cadence.md` and the issue tracker.
- [ ] Every roadmap task has an issue number, and its box matches the issue state (`complete` phases
      have all boxes checked).
- [ ] `notes/backlog.md` names every open gap, its status, its evidence, and a target phase; gaps that
      landed are marked `done`; new gaps discovered during work are added.
- [ ] `CHANGE_LOG.md` has one dated entry per milestone, and the entries match the merged work and the
      roadmap status.
- [ ] The "Detailed Next Steps Notes" in `ROADMAP.md` reflect the latest completed and active phases.
- [ ] `python scripts/dashboard.py` (the validator and the docs build included) is green.

## First sync (2026-10-15)

- P4 is `complete`; all its task and subtask boxes are checked and its child issues (#37 to #42) are
  closed. P5 is `active` with parent #44 and tasks #45 to #50; #45 and #46 are closed (P5.1, P5.2).
- `notes/backlog.md` was reviewed: the MKRF canonical model, the C5 route model and patch accounts, and
  the spatial gaps are `done`; the performance work is deferred with a plan
  (`notes/design/ws4-performance.md`); the remaining items carry target phases.
- `CHANGE_LOG.md` is current through the P4 release and the P5 launch, and every milestone has an entry.
- `scripts/check_workflow.py`: `0 error(s), 0 warning(s)`; the dashboard is `OVERALL: GREEN`.
