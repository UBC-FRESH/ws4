# P100 condition-card provenance — close-out package

Phase: P100
Parent issue: #670
Pull request: #690
Evidence head: `P100.1`
Status: pr-open; awaiting review

## Recommendation

Approve the uncertainty/provenance display in the condition panel. Keep the card
read-only and advisory. Merge after CI is green.

## Acceptance

- Uncertainty column: met.
- Missing uncertainty shows `not stated`: met.
- Provenance block: met.
- 71 web tests and Sphinx: met.
- Dashboard all seven gates: green.
- Separate worktree; P87/P89/P95/P96 untouched.

## Limits

- One report surface, not a general provenance system. `DEC-03` remains shortlisted.
- Cards remain review-required/advisory.

## Decision

Approve and merge after green CI. Do not present the card as operational.
