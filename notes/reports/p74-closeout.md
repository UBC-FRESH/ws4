# Phase close-out report: P74 Live map hardening

Phase: P74, Live map hardening
Parent issue: #531
Pull request: #535, `feature/p74-live-map-hardening` into `main`
Evidence head: `d1ea370`, the head that CI run `40618407600` covers
Report commit: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-28
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #535, and delete `feature/p74-live-map-hardening`.
2. Close task issues #532, #533, and #534, then parent issue #531, with a closeout comment
   that cites the merge commit.
3. Deploy `v82` to the live services.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Panning or zooming does not drop treated-block colours. | Live smoke pans the MapLibre canvas; status remains `live`, counts remain nonzero, and the schedule is reapplied after the viewport load. | Met |
| Live/Static toggles between the current schedule and the static treatment map. | Map-legend checkbox: uncheck shows static MVT and counts; check restores live counts and status. | Met |
| Counts and legend match the active mode. | Live mode shows schedule counts/full total with `Live ·` legend title; static mode shows run MVT counts with the static title. | Met |
| The toggle is keyboard-accessible and hidden when no run is active. | It is a native checkbox inside the map legend, created only while `state.live.active`. | Met |
| Target charts continue to update live in either map mode. | They use the independent `targets` SSE stream; the live smoke records a changed achieved readout. | Met |
| c5 and TSA 46 smoke pass. | `check_live_map.py` passes on both services, including pan and toggle transitions. | Met |
| `python scripts/dashboard.py` is green. | All seven gates green at `d1ea370`; CI run `40618407600` success. | Met |

The full schedule is reapplied by `applyLiveSchedule()` after a live MVT load. The source URL is
changed back to the treatment layer for static mode, and to the bare block layer for live mode.

## 2. Workflow compliance

- Parent issue before the branch: #531 created before `feature/p74-live-map-hardening`.
- Branch from `main`: forked from `c3764d7` (P73 status).
- Commit messages: both start with P74 task IDs.
- Child issues: #532, #533, and #534 are linked as sub-issues and are closed after merge.
- Approval gates: the user approved P74; merge approval remains outstanding.

## 3. Gate evidence

`python scripts/dashboard.py` at `d1ea370`:

| Gate | Result | Seconds |
| --- | --- | --- |
| lint | GREEN | 0.11 |
| format | GREEN | 0.11 |
| types | GREEN | 26.99 |
| tests | GREEN | 142.95 |
| validator | GREEN | 0.86 |
| docs | GREEN | 16.23 |
| docstrings | GREEN | 2.87 |

Overall: GREEN.

`scripts/check_live_map.py`:

- Starts a real short run.
- Waits for live counts and a target-chart change.
- Drags the map and verifies live mode and nonzero counts.
- Switches to static, verifies the static count, returns to live, then stops the run and verifies
  the static map returns.
- Passes on c5 `run-dated3` and TSA 46 `baseline`.

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 40618407600 | `d1ea370` | success | Quality gates, dashboard summary, notebook outputs, clean-checkout contract, and pre-commit parity all green. |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Static mode can take several seconds on TSA 46. | It reloads the treatment MVT source while the solver is active. | The map shows the existing loading overlay; the live smoke waits for a non-live, non-loading status before asserting. |
| The toggle is MapLibre-only. | The SVG fallback has no MVT source; it always follows the live schedule. | The checkbox is created only for the MapLibre engine. |

## 6. Next phase

No P75 is scoped. The next recommended surface is **Search artifact cross-linking**: make a Pareto
member's schedule, targets, metrics, and report files readable in one compact detail view.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
