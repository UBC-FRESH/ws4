# Phase close-out report: P23 Accounts and target activation

Phase: P23, Accounts and target activation
Parent issue: #206
Task issue: #195 (P23.1)
Pull request: #212
Evidence head: `1526216`
Report commit: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-24
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #212, and delete the branch `feature/p23-target-browser`.
2. Close task issue #195 and parent issue #206 with closeout comments that cite the merge commit.
3. P24, Search portfolio and multi-objective, was launched by the maintainer while this phase was in
   review; this phase takes no launch action.

Settings changes: none. This phase changes no repository setting, tag, release, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A user can find an account by substring without knowing the full name. | The tree filters on the lower-cased substring. The Playwright check searched `CWH_HW_M` and found two accounts; the live TSA 46 search found the same two. | Met |
| Every account in the run's `account_values.csv` is reachable. | The tree is built from `/api/runs/<run>/accounts`; the TSA 46 benchmark exposes 51 unique accounts and the browser rendered 51 leaves. | Met |
| Adding a target writes a valid YAML document and the new row appears in the Targets table. | `scripts/check_target_browser.py` added a target (rows 1 to 2), the API returned both rows, the YAML was valid, and the row rendered. An empty-file service accepted the first target with width 10. | Met |
| An already-targeted account is visibly marked. | The leaf renders a `target` badge; `accountIsTarget` drives it from `state.targets`. The check saw the badge after the add. | Met |
| A run started from the UI uses the new target. | On the c5 sample, a target added in the Targets tab (`feature.Area.managed.CDCONMIX`, period 1) was written to the YAML; Play started a 3-iteration run, and the run's `report_targets.csv` contained that account with period 1. | Met |
| The last target is removable. | The API refuses an empty `targets` document, so the browser disables removal of the last row and documents the YAML edit. | Not met; deliberate guard |
| `python scripts/dashboard.py` is green. | Lint, format, types, tests, validator, docs, and docstrings pass at `1526216`. | Met |

## 2. Workflow compliance

- Parent issue before the branch: #206 was created before `feature/p23-target-browser`;
  task #195 is linked as a sub-issue.
- Branch from `main`: the branch starts at `3c6ae67`, which includes P22.
- Commit messages start with task IDs: `P23.1`.
- Gates for each commit: the dashboard is green at the evidence head.
- Roadmap and changelog in step: P23 and P23.1 are recorded; the changelog records the result and
  the dashboard.
- Task issue: the body carries the task identifier, parent, branch, status, and acceptance.
- Approval gates: the phase opened pull request #212 and did not merge, tag, release, or change a
  setting. It closed the superseded map PR #204, which carried the same base-URL fix at `v48`; the
  fix is now in #212 at `v50`.

## 3. Gate evidence

| Gate | Result at `1526216` |
| --- | --- |
| lint | green |
| format | green |
| types | green |
| tests | green (53 web tests; full suite in the dashboard) |
| validator | green |
| docs | green |
| docstrings | green |

## 4. CI evidence

The pull request is opened with this report. Its first CI run is posted on pull request #212.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The last target cannot be removed in the browser. | `POST /api/targets.json` refuses an empty list because the optimizer needs at least one target. | The remove control is disabled and the reason is documented; the YAML or `Put targets` remains the route for removing the last target. |
| The YAML writer drops comments and key order. | The endpoint validates with the optimizer's loader and writes with `yaml.safe_dump`; a comment-preserving writer is not a dependency. | Target `notes` are preserved through the JSON round-trip and covered by a test; the web reference states the comment limitation. |
| The width defaults to ten years when the file is empty. | An empty file has no width to inherit, and ten years is the planning convention used by the benchmark targets. | The form exposes the width; the user can change it before adding. |
| The account tree covers the run's accounts, not accounts that exist only in the dataset. | The acceptance criterion names `account_values.csv`; dataset-only accounts have no value to show. | A later dataset-catalogue view can merge them when the need is concrete. |
| The display period groups the zero-based first slice as "Period 1", while a target period is one-based. | Pre-existing grouping in `/api/runs/<run>/periods`; this phase did not change the optimizer's period semantics. | The form hint states that period 1 is the first accounting period; the mismatch is recorded as a follow-up, not silently changed. |
| The phase also carries the map shell cache fix. | The target browser could not be validated through `?v=...` while the base URL swallowed the page query. | The fix is included at `v51`, documented, and PR #204 is closed as superseded. |
| Play did nothing on the MapLibre map. | The Play and Stop listeners were installed inside `fit()`, the SVG-only bounds helper; a MapLibre page never called it. The c5 test reproduced the failure: no `POST /api/runs` and no button change. | Moved the listeners to `wireControls` and added `scripts/check_run_controls.py`; the c5 run then posted, switched to Pause, showed progress, and wrote the new target to `report_targets.csv`. |
| The c5 service can start a run that fails on a configuration gap. | `--patch-accounts` without `--topology` reached the optimizer, which tried to read `.` as a CSV and exited with `IsADirectoryError`. | The service refuses the combination with a named error; the optimizer also names the missing topology; tests cover both. Legacy c5 runs with `year`/`period` columns remain a separate compatibility follow-up; UI testing uses a clean runs directory of current-schema runs. |

## 6. Verification commands

```bash
python scripts/dashboard.py
python scripts/check_target_browser.py http://127.0.0.1:8021/ --search CWH_HW_M
python scripts/check_run_controls.py http://127.0.0.1:8022/ --iterations 3
python scripts/check_map_browser.py 'http://127.0.0.1:8017/?v=51' --wait-ms 30000
```

The first is the gate. The second ran against a scratch targets file and left one target because
the check started with one; it added and removed the second. The third opened the live TSA 46 service
and made 12 MVT requests at `v=v8` with no console errors.

## 7. Next phase

The maintainer redirected the phase after P22 to the account/target browser (this P23), so the
search-portfolio proposal moved to P24. P24 was then launched while this phase was in review (parent
#207, pull request #213); this phase does not launch it.

P24 delivers the elite archive and Pareto front, the target-weight portfolio runner, the grid/random
tuner, and LP dual/reduced-cost sensitivity. Its tasks are P24.1 to P24.4 in `ROADMAP.md`. The
recommended defaults remain: keep goal programming as the objective, keep the tuners opt-in, and
treat LP duals as advisory.
