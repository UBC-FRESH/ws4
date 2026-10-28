# Phase close-out report: P73 Live map updates

Phase: P73, Live map updates
Parent issue: #525
Pull request: #529, `feature/p73-live-map` into `main`
Evidence head: `9328212`, the head that CI run `40611012972` covers
Report commit: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-28
Status: merged and closed on 2026-10-28 as `6e3b29b`.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #529, and delete `feature/p73-live-map`.
2. Close task issues #526, #527, and #528, then parent issue #525, with a closeout comment
   that cites the merge commit.
3. Deploy `v81` to the live services.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| MapLibre blocks recolor while the solver runs. | c5 live run: counts changed from 0 to 70+ while active; red treated blocks visible. TSA 46: counts changed from 0 to 218/356/420 while active. | Met |
| Treated counts change without a page reload. | Live MapLibre status reports `live · 12,567 blocks` and counts update from the SSE schedule; no reload. | Met |
| Island/reset schedule events rebuild the live map. | The schedule handler clears feature state on `reset` and applies the replacement changed set. | Met |
| The static map returns after finish. | `check_live_map.py` asserts the status leaves `live` and the static counts/map return after stop/finish. | Met |
| Target charts continue to update live. | The live smoke records a changed achieved readout while the same run is active. | Met |
| Live mode is usable on c5 and TSA 46. | `check_live_map.py` passes on both services. | Met |
| `python scripts/dashboard.py` is green. | All seven gates green at `9328212`; CI run `40611012972` success. | Met |

The implementation uses MVT feature ids and MapLibre feature state, not a GeoJSON refetch on every
schedule event. The live map uses the bare blocks layer while active and returns to the treatment
MVT layer when the run finishes.

## 2. Workflow compliance

- Parent issue before the branch: #525 created before `feature/p73-live-map`.
- Branch from `main`: forked from `d9a40d6` (P72 status).
- Commit messages: all start with P73 task IDs.
- Child issues: #526, #527, and #528 are linked as sub-issues and are closed after merge.
- Approval gates: the user approved investigating live updates and then starting P73; merge approval
  remains outstanding.

## 3. Gate evidence

`python scripts/dashboard.py` at `9328212`:

| Gate | Result | Seconds |
| --- | --- | --- |
| lint | GREEN | 0.10 |
| format | GREEN | 0.11 |
| types | GREEN | 13.95 |
| tests | GREEN | 141.83 |
| validator | GREEN | 0.85 |
| docs | GREEN | 16.86 |
| docstrings | GREEN | 2.74 |

Overall: GREEN.

`scripts/check_live_map.py`:

- c5 `run-dated3`: live counts changed, pinned target chart achieved value changed, static map
  returned after the run.
- TSA 46 `baseline`: same checks after the initial map load.

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 40611012972 | `9328212` | success | Quality gates, dashboard summary, notebook outputs, clean-checkout contract, and pre-commit parity all green. |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Live counts are full-run schedule counts, not the viewport sample. | The schedule is authoritative for the solver state and matches the target table. | The map visual is clipped to loaded features; the counts and legend name the live schedule. |
| The live path uses the bare `blocks` MVT layer. | A treatment layer at low zoom can omit untreated blocks and cannot show new scheduled blocks. | Feature state colors the current schedule over the bare block geometry; the static treatment layer returns after finish. |
| Tile cache version was bumped. | Existing v8 tiles lack feature ids needed for live state. | `TILE_CACHE_VERSION` and the client tile version are `v9`; old tiles are ignored. |

## 6. Next phase

No P74 is scoped. The next recommended surface is **live map history**: a compact time strip of the
best-island schedule changes and a toggle to inspect the pre-run treatment layer beside the live
schedule. It should keep the feature-state path and not add per-event tile requests.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
