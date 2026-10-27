# Phase close-out report: P70 Target table polish

Phase: P70, Target table polish
Parent issue: #504
Pull request: #508, `feature/p70-target-table` into `main`
Evidence head: `35b3dff`, the head that CI run `40557044057` covers
Report commit: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-27
Status: merged and closed on 2026-10-27 as `cd2b113`.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #508, and delete `feature/p70-target-table`.
2. Close task issues #505, #506, and #507, then parent issue #504, with a closeout comment
   that cites the merge commit.
3. Deploy `v78` to the live services.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Account labels are compact and the full path remains available. | c5 and TSA 46 show labels such as **Yield · managed · Conifer**, a root badge, and the full account in the title. | Met |
| Units are shown only when confidently inferred. | c5 targets show `m³`; the helper also infers `ha`, `%`, `tC`, and `tCO2e`; unknown names stay blank. | Met |
| Period labels distinguish per-period and whole-horizon targets. | c5 table shows **All / year 9** and **P2 / year 20**, **P3 / year 30**, and so on. | Met |
| Status is visible inline and updates during live runs. | Status chips show met, below min, above max, off, or —. A one-iteration c5 run changed the first rows from met/met below-min to below-min/above-max. | Met |
| Sorting preserves unsaved edits and reports the direction. | Account and status sorts pass; an edited Min survives sorting; `aria-sort` matches; **File order** resets; save/reload smoke passes on a scratch targets file. | Met |
| Target charts and saved targets are unchanged. | Target-chart smoke and target editing save/reload smoke pass. | Met |
| Desktop and iPad landscape remain usable. | The table fits 1024 px with fixed compact columns and no page overflow; 1500 px uses the wider layout. | Met |
| `python scripts/dashboard.py` is green. | All seven gates green at `35b3dff`; CI run `40557044057` success. | Met |

The **Min w** and **Max w** inputs moved from the main row to the expandable detail row to keep
the status column visible at iPad landscape width; the save payload is unchanged.

## 2. Workflow compliance

- Parent issue before the branch: #504 created before `feature/p70-target-table`.
- Branch from `main`: forked from `e2f980f` (DIS-04 recovery scenario).
- Commit messages: all start with P70 task IDs.
- Child issues: #505, #506, and #507 are linked as sub-issues and are closed after merge.
- Approval gates: the user approved starting P70; merge approval remains outstanding.

## 3. Gate evidence

`python scripts/dashboard.py` at `35b3dff`:

| Gate | Result | Seconds |
| --- | --- | --- |
| lint | GREEN | 0.07 |
| format | GREEN | 0.08 |
| types | GREEN | 0.58 |
| tests | GREEN | 142.77 |
| validator | GREEN | 0.94 |
| docs | GREEN | 4.39 |
| docstrings | GREEN | 2.84 |

Overall: GREEN.

`scripts/check_target_table.py`:

- c5 `run-base` and TSA 46 `baseline`: labels, roots, units, period labels, status, sorting,
  edit preservation, and 1024 px layout.
- The script changes only the browser DOM and never clicks Save.

Manual live run on c5:

- Before: `met, met, below min, below min, ...`
- After a one-iteration run: `below min, above max, below min, ...`

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 40557044057 | `35b3dff` | success | Quality gates, dashboard summary, notebook outputs, clean-checkout contract, and pre-commit parity all green. |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Min/Max weights moved to the detail row. | Seven main columns plus status did not fit the 1024 px sidebar. | The weights are still editable and still save through the same target payload. |
| The table uses fixed compact columns at 1024 px. | iPad landscape has a narrow sidebar; a fluid table pushed Status off-screen. | The account path stays in the title; status remains visible. |

## 6. Next phase

No P71 is scoped. The next recommended surface is **search/report cross-linking**: open a
Pareto-front member's schedule, accounts, and target status from one place, or a compact
"run health" summary above the target charts.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
