# Phase close-out report: P72 Results run health and cross-links

Phase: P72, Results run health and cross-links
Parent issue: #518
Pull request: #522, `feature/p72-results-health` into `main`
Evidence head: `aa84c1b`, the head that CI run `40597570859` covers
Report commit: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-27
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #522, and delete `feature/p72-results-health`.
2. Close task issues #519, #520, and #521, then parent issue #518, with a closeout comment
   that cites the merge commit.
3. Deploy `v80` to the live services.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Health counts match the Plan target summary. | c5 `run-dated3` and TSA 46 `baseline`: the health failing count matches the Plan summary after **Show failing targets**. | Met |
| Show failing targets opens Plan with the failing filter active. | Browser smoke asserts the Plan workspace, `failing` status, visible rows, and matching summary. | Met |
| Compare target account links open Plan with the account filtered. | Browser smoke activates the account cell link and asserts the Plan account search contains the full account. | Met |
| Compare target rows have one account cell and aligned columns. | Each row has exactly eight cells; the account cell is the first, with `role=button`. The duplicate-append audit found no second account cell at the evidence head. | Met |
| Results is usable at 1024 px. | Browser smoke asserts the health card is visible and the page has no horizontal overflow at 1024×768. | Met |
| Target and map behavior is unchanged. | Target-chart, map-hierarchy, and target-triage smokes pass. | Met |
| `python scripts/dashboard.py` is green. | All seven gates green at `aa84c1b`; CI run `40597570859` success. | Met |

The health card shows run id, kind, period, target counts, pinned chart count, and LiDAR/Carbon
availability across Reports, Compare, and Search.

## 2. Workflow compliance

- Parent issue before the branch: #518 created before `feature/p72-results-health`.
- Branch from `main`: forked from `6f0a3c2` (P71 status).
- Commit messages: both commits start with P72 task IDs.
- Child issues: #519, #520, and #521 are linked as sub-issues and are closed after merge.
- Approval gates: the user approved starting P72; merge approval remains outstanding.

## 3. Gate evidence

`python scripts/dashboard.py` at `aa84c1b`:

| Gate | Result | Seconds |
| --- | --- | --- |
| lint | GREEN | 0.12 |
| format | GREEN | 0.11 |
| types | GREEN | 28.03 |
| tests | GREEN | 143.52 |
| validator | GREEN | 0.83 |
| docs | GREEN | 16.15 |
| docstrings | GREEN | 2.81 |

Overall: GREEN.

`scripts/check_results_health.py`:

- c5 `run-dated3` and TSA 46 `baseline`: health counts, failing action, Compare account link,
  eight-cell rows, and 1024 px.
- No target save is triggered.

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 40597570859 | `aa84c1b` | success | Quality gates, dashboard summary, notebook outputs, clean-checkout contract, and pre-commit parity all green. |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Health counts are derived from the loaded target table and realized target values. | There is no separate health endpoint, and duplicating the target reader would drift. | The health card refreshes from the same target summary and live snapshots; the browser smoke checks the counts against Plan. |
| Compare account links filter the current Plan target table. | Compare rows include accounts that may not have a target. | The filter is an exact account search; a non-target account legitimately shows `0 of N visible`. |

## 6. Next phase

No P73 is scoped. The next recommended surface is **Search artifact cross-linking**: turn a Pareto
member into a compact run summary with its schedule, targets, metrics, and report files in one
place, without pretending the artifact is a full run directory.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
