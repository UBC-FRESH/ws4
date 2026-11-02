# P94 condition-card provenance — close-out package

## Header

Phase: P94
Parent issue: #670
Pull request: TBD
Evidence head: `P94.1` on `feature/p94-condition-provenance`
Report date: 2026-11-02
Status: pr-open; awaiting review

## Recommendation

1. Approve the uncertainty/provenance display in the condition panel.
2. Keep the card read-only and advisory.
3. Merge after CI is green.

## Acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Uncertainty column | JS table and static assertion | met |
| Missing value displays `not stated` | JS branch | met |
| Provenance block | JS text-node list | met |
| Tests/docs | 71 web tests; web reference | met |
| Dashboard | all seven gates green | met |
| PR queued | TBD | pending |

## Workflow compliance

- Parent #670 and child #671 exist and are linked.
- Branch `feature/p94-condition-provenance` in a separate worktree at
  `/srv/shared-data/gep/ws4/tmp/ws4-p94`; P87/P89 untouched.
- Commit starts with `P94.1`.
- No objective, constraint, growth, schedule, solver, tag, or release change.

## Gate evidence

`python scripts/dashboard.py` -> **OVERALL: GREEN** on all seven gates.

## CI evidence

To be recorded after the PR opens.

## Deviations and risks

- This is one report surface, not a general provenance system across all WS4
  reports. `DEC-03` remains shortlisted for broader badges/bands.
- Cards remain review-required and advisory.

## Decision

Approve and merge after green CI. Do not present the card as operational.
