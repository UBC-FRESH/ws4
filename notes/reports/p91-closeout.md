# P91 condition card from a WS4 run — close-out package

## Header

Phase: P91
Parent issue: #655
Pull request: TBD
Evidence head: `P91.1` commit on `feature/p91-condition-run-card`
Report date: 2026-11-02
Status: pr-open; awaiting review

## Recommendation

1. Approve the account-derived condition-card consumer.
2. Keep all derived indicators `review_required`; this is not a validated condition model.
3. Merge after CI is green.
4. Leave real condition sources and operational alerting to `DIS-03`.

## Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Account-derived card builder | `build_report_from_accounts` | met |
| CLI command | `ws4 condition-card` | met |
| JSON and Markdown output | CLI test | met |
| Bad input rejection | focused tests | met |
| Derived indicators marked review-required | builder and test | met |
| Dashboard green | all seven gates | met |
| PR queued | TBD | pending |

## Workflow compliance

- Parent #655 and child #656 exist and are linked.
- Branch `feature/p91-condition-run-card` from `origin/main` in a separate
  worktree at `/srv/shared-data/gep/ws4/tmp/ws4-p91`.
- Parallel work was explicitly authorised by the maintainer; P87/P89 were not
  modified.
- Commit subject starts with `P91.1`.
- Roadmap, changelog, docs, design note, and tests are in the change set.
- No objective, constraint, growth, schedule, solver, tag, or release change.

## Gate evidence

`python scripts/dashboard.py` -> **OVERALL: GREEN**:

- lint
- format
- types
- tests
- validator
- docs
- docstrings

Focused tests: 13 passed.

## CI evidence

To be recorded after the phase pull request is opened.

## Deviations and risks

- Account-derived values are a reporting view, not independent condition
  validation.
- The card has no RMSE for derived accounts and marks them `review_required`.
- No real `DIS-03` condition source or operational alerting is included.

## Next phase

No next phase until this consumer is reviewed. `DEC-02` remains shortlisted;
real condition sources and UI are separate work.

## Decision

Approve the review-required account consumer and merge after green CI. Do not
present derived cards as operational early warning.
