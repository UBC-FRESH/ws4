# Phase close-out report: P71 Target triage

Phase: P71, Target triage
Parent issue: #511
Pull request: #516, `feature/p71-target-triage` into `main`
Evidence head: `eb47bb9`, the head that CI run `40575401627` covers
Report commit: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-27
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #516, and delete `feature/p71-target-triage`.
2. Close task issues #512, #513, and #514, then parent issue #511, with a closeout comment
   that cites the merge commit.
3. Deploy `v79` to the live services.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Failing targets are the first thing the summary reports. | c5 `run-base`: **9 targets · 5 failing · 4 met · 0 off**; chart header repeats **5 failing · 4 met**. | Met |
| Filtering shows only matching rows and reports visible/total counts. | Failing filter: `5 of 9 visible`, all visible chips below/above. Account search combines with it (`2 of 9`), and Clear restores `9 visible`. | Met |
| Filtering does not alter saved data or unsaved input values. | An edited Min stays `777777` while status and account filters narrow and clear; hidden rows remain in the DOM and save payload. | Met |
| Bulk pin updates the chart canvas and watch panel. | Pin failing checks every visible failing row and creates charts; Unpin visible clears them. Hidden rows keep their pin state. | Met |
| The controls are usable by keyboard and at 1024 px. | Native search/select/buttons; browser smoke asserts no page overflow and visible toolbar/summary at 1024×768. | Met |
| Target charts and target YAML are unchanged. | Target-chart smoke passes; map hierarchy smoke passes. | Met |
| `python scripts/dashboard.py` is green. | All seven gates green at `eb47bb9`; CI run `40575401627` success. | Met |

Live summary update on c5: a one-iteration run changed **5 failing / 4 met** to
**6 failing / 3 met**.

## 2. Workflow compliance

- Parent issue before the branch: #511 created before `feature/p71-target-triage`.
- Branch from `main`: forked from `495ee85` (P70 status).
- Commit messages: both commits start with P71 task IDs.
- Child issues: #512, #513, and #514 are linked as sub-issues and are closed after merge.
- Approval gates: the user approved starting P71; merge approval remains outstanding.

## 3. Gate evidence

`python scripts/dashboard.py` at `eb47bb9`:

| Gate | Result | Seconds |
| --- | --- | --- |
| lint | GREEN | 0.12 |
| format | GREEN | 0.10 |
| types | GREEN | 26.60 |
| tests | GREEN | 140.00 |
| validator | GREEN | 0.86 |
| docs | GREEN | 16.75 |
| docstrings | GREEN | 2.98 |

Overall: GREEN.

`scripts/check_target_triage.py`:

- c5 `run-base` and TSA 46 `baseline`: summary, status/account filters, edit preservation,
  bulk pin/unpin, and 1024 px.
- No Save click; the check is non-destructive.
- Console errors are ignored only for failed resource loads.

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 40575401627 | `eb47bb9` | success | Quality gates, dashboard summary, notebook outputs, clean-checkout contract, and pre-commit parity all green. |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Filters are view-only. | Server-side target filtering would add a second query path and risk edits. | Rows stay in the DOM; filters only hide them, preserving the existing save contract. |
| Bulk pin is scoped to **visible** failing rows. | The filter is the analyst's triage context. | Hidden failing rows keep their existing pin state; clearing the filter makes them selectable again. |

## 6. Next phase

No P72 is scoped. The next recommended surface is **Results cross-linking**: open a Pareto
member's schedule, account report, target status, and map from one place, with a compact run-health
summary above the compare/search views.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
