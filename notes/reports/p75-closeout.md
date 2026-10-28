# Phase close-out report: P75 Live run attach and reconnect

Phase: P75, Live run attach and reconnect
Parent issue: #537
Pull request: #541, `feature/p75-live-attach` into `main`
Evidence head: `b9c4e42`, the head that CI run `40645760372` covers
Report commit: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-28
Status: queued for approval. Not merged.

## Recommendation

1. Squash-merge pull request #541 and delete `feature/p75-live-attach`.
2. Close tasks #538–#540 and parent #537 with the merge commit.
3. Deploy `v83` to the live services.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A CLI/API-started live run is found after page load. | A run started through `POST /api/runs` is discovered in `/api/summary` before it has a summary; an unqualified page load selects it. | Met |
| Target charts update from its target snapshots. | The attach smoke waits for a non-empty achieved readout and observes it change while the run is active. | Met |
| The live map attaches and updates. | The same run shows `live · … blocks` and nonzero treated counts after attach. | Met |
| Refresh and transient reconnect restore the stream and replay state. | `check_live_attach.py` reloads mid-run, reconnects, and finds live charts and map again. | Met |
| A finished run returns to static mode. | Status leaves `live`; P74's static-return path is reused. | Met |
| `python scripts/dashboard.py` is green. | All seven gates green at `b9c4e42`; CI run `40645760372` success. | Met |

The live shell now attaches after page load and run change, opens the same SSE helper used by
`Solve`, and replays current target/schedule snapshots. Running search runs are exposed in the run
list before `summary.json` exists. While a run has no `account_values.csv`, target charts derive
their period grid and target cells from the target document; the achieved values arrive over SSE.
The Plan header shows a **LIVE** badge.

## 2. Workflow compliance

- Parent issue before the branch: #537 created before `feature/p75-live-attach`.
- Branch from `main`: forked from `d06818a` (P74 status).
- Commit messages: all start with P75 task IDs.
- Child issues: #538–#540 are linked as sub-issues and are closed after merge.
- Approval gates: the user approved P75; merge approval is covered by that approval.

## 3. Gate evidence

`python scripts/dashboard.py` at `b9c4e42`: lint 0.07 s, format 0.06 s, types 0.70 s,
tests 145.38 s, validator 1.03 s, docs 3.51 s, docstrings 2.92 s. Overall **GREEN**.

`scripts/check_live_attach.py` passes on c5 and TSA 46. It starts a run through the API, opens the
shell by run URL, verifies live charts and map, reloads, and verifies reattachment. The run is
stopped in cleanup.

Manual unqualified page load also selected a newly started external run automatically.

## 4. CI evidence

| Run ID | Head commit | Conclusion |
| --- | --- | --- |
| 40645760372 | `b9c4e42` | success |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Running runs have no `summary.json`/account values yet. | The optimizer writes them at finish. | `/api/summary` includes telemetry-backed runs, and target charts fall back to target-row periods/cells until SSE series arrive. |
| Auto-selection checks at most the ten newest search runs. | Scanning every historical run on page load would be wasteful. | A running run outside that window can still be selected explicitly; the newest run is the normal case. |

## 6. Next phase

P76 will clean the c5 sample run set and add the 20×10-year even-flow baseline scenario with a
90% final growing-stock floor.

## 7. Decision

- [x] Approve as written.
