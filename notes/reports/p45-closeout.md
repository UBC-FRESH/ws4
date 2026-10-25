# Phase close-out report: P45 Route evaluation performance

Phase: P45, Route evaluation performance
Parent issue: #368
Pull request: this P45 PR
Status: queued for approval. Not merged.
Date: 2026-10-25

## Recommendation

1. Squash-merge the P45 pull request and delete `feature/p45-route-profile`.
2. Close task #369 and parent #368.
3. Approve P46 for the incremental ledger implementation only if the design is accepted.

Settings changes: none.

## Acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Repeatable profile reports seconds/eval and top costs. | c5, 32 blocks: 0.451 s/evaluation; `simulate` 0.407 s. | Met |
| Design names fallback conditions and invariants. | `notes/design/ws4-incremental-route.md` names delivery, planned opening, other accounts and seven invariants. | Met |
| Parity plan covers build, maintenance, haul, volume, delivery. | Design note's P46 test list. | Met |
| Dashboard green. | Green at the report commit. | Met |

## Deviations

- This phase deliberately does not implement the ledger. The profile shows the hot path
  is the full simulator, so implementation belongs in P46 after review.
- The profile uses a c5 run schedule and the c5 production route config; GBR parity is
  deferred to P46.
