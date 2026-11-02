# P95 condition-card provenance — close-out package

Phase: P95
Parent issue: #670
Pull request: TBD
Evidence head: `P95.1` on `feature/p95-condition-provenance`
Status: pr-open; awaiting review

## Recommendation

Approve the uncertainty/provenance display in the condition panel. Keep the
card read-only and advisory. Merge after CI is green.

## Acceptance

- Uncertainty column: met.
- Missing uncertainty shows `not stated`: met.
- Provenance block: met.
- 71 web tests and Sphinx: met.
- Dashboard all seven gates: green.

## Compliance

- Parent #670 and child #671 are linked.
- Separate worktree; P87/P89/P94 untouched.
- Commit starts with `P95.1`.
- No objective, constraint, growth, schedule, solver, tag, or release change.

## Limits

- One report surface, not a general provenance system. `DEC-03` remains shortlisted.
- Cards remain review-required/advisory.

## Decision

Approve and merge after green CI. Do not present the card as operational.
