# P92 condition-card API — close-out package

## Header

Phase: P92
Parent issue: #659
Pull request: https://github.com/UBC-FRESH/ws4/pull/661
Evidence head: `P92.1` commit on `feature/p92-condition-card-api`
Report date: 2026-11-02
Status: pr-open; awaiting review

## Recommendation

1. Approve the read-only condition-card API.
2. Keep derived cards review-required and report-only.
3. Merge after CI is green.
4. Leave front-end rendering and real condition sources separate.

## Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Endpoint added | `GET /api/runs/{run}/condition-card` | met |
| Valid run returns a P90 card | API test | met |
| 404 for missing accounts | API test | met |
| 422 for invalid accounts | API test | met |
| Review-required indicators | API test | met |
| Tests and dashboard | 71 web tests; dashboard green | met |
| PR queued | #661 | met |

## Workflow compliance

- Parent #659 and child #660 exist and are linked.
- Branch `feature/p92-condition-card-api` from `origin/main` in a separate
  worktree at `/srv/shared-data/gep/ws4/tmp/ws4-p92`.
- Parallel work was explicitly authorised; P87/P89 were not modified.
- Commit subject starts with `P92.1`.
- Roadmap, changelog, web reference, tests, and endpoint are in the change set.
- No objective, constraint, growth, schedule, solver, tag, or release change.

## Gate evidence

`python scripts/dashboard.py` -> **OVERALL: GREEN** on lint, format, types,
tests, validator, docs, and docstrings.

## CI evidence

PR #661 is open; check CI on the final head.

## Deviations and risks

- The endpoint derives `review_required` indicators from accounts; it is not a
  condition validation.
- Front-end rendering and `DIS-03` condition sources are not included.

## Decision

Approve the read-only endpoint and merge after green CI. Do not present it as
operational early warning.
