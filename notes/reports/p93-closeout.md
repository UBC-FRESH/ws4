# P93 condition-card Reports UI — close-out package

## Header

Phase: P93
Parent issue: #662
Pull request: https://github.com/UBC-FRESH/ws4/pull/669
Evidence head: `P93.1` commit on `feature/p93-condition-card-ui`
Report date: 2026-11-02
Status: pr-open; awaiting review

## Recommendation

1. Approve the Reports-tab condition-card panel.
2. Keep the card read-only and advisory; do not add editing or alert automation.
3. Merge after CI is green.

## Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Panel and button in HTML | `test_web` assertions | met |
| Fetches P92 endpoint | `loadConditionCard` | met |
| Text-node rendering | no HTML interpolation | met |
| Error/empty messages | JS branches | met |
| Docs | web reference | met |
| Tests/dashboard | 71 web tests; dashboard green | met |
| PR queued | #669 | met |

## Workflow compliance

- Parent #662 and child #663 exist and are linked.
- Branch `feature/p93-condition-card-ui` from `origin/main` in a separate worktree
  at `/srv/shared-data/gep/ws4/tmp/ws4-p93`.
- Parallel work explicitly authorised; P87/P89 untouched.
- Commit starts with `P93.1`.
- No objective, constraint, growth, schedule, solver, tag, or release change.

## Gate evidence

`python scripts/dashboard.py` -> **OVERALL: GREEN** on lint, format, types,
tests, validator, docs, and docstrings.

## CI evidence

PR #669 is open; check CI on the final head.

## Deviations and risks

- The browser fetches account-derived cards; these remain `review_required`.
- No real condition source or `DIS-03` alerting is included.
- No browser automation beyond HTML presence and JS syntax.

## Decision

Approve the read-only panel and merge after green CI. Do not present it as
operational early warning.
