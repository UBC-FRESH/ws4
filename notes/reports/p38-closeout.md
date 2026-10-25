# Phase close-out report: P38 Account browser polish

Phase: P38, Account browser polish
Parent issue: #293
Pull request: this P38.1 PR
Status: queued for approval. Not merged.
Date: 2026-10-25

## Recommendation

1. Squash-merge the P38.1 pull request and delete `feature/p38-account-polish`.
2. Close task #294 and parent #293.

Settings changes: none.

## Acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Full account names are visible. | Leaf text is the full name. | Met |
| Search reports matched/total counts. | `#account-count` in the tree header. | Met |
| The tree is keyboard-navigable. | Enter selects the first match; arrows move and Escape returns to search. | Met |
| Map labels use year ranges; target rows say "Target period". | `_run_periods` labels and the table header changed. | Met |
| Dashboard green. | Green at the report commit. | Met |

## Deviations

- The optimizer period remains one-based; only the display labels changed.
- Full names make the tree denser; ellipsis and title retain the readable value.
