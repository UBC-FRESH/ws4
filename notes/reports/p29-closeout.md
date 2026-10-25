# Phase close-out report: P29 MIP lane and exact small-instance validation

Phase: P29, MIP lane and exact small-instance validation
Parent issue: #238
Pull request: not opened yet
Evidence head: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-25
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge the P29 pull request, and delete the branch `feature/p29-mip`.
2. Close parent issue #238 with a closeout comment that cites the merge commit.
3. Launch P30, Dataset provenance and model limitations: populate the TSA 46/47 manifest
   metadata, make the P26 data-quality block report `ok`, and publish the model-limitations page.

Settings changes: none. This phase changes no repository setting, tag, release, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| `ws4 solve-mip` writes a schedule, summary, target report, and explicit model status. | The command writes `mip.json`, `schedule.csv`, `account_values.csv`, and `report_targets.csv`; `mip.json` names the option-selection boundary. | Met |
| The exact-vs-heuristic report compares actual target penalties and names the gap. | `scripts/exact_vs_heuristic.py` runs both lanes, replays both schedules, and writes JSON/Markdown with the gap. | Met |
| `--lp-bound` records the LP bound and gap; scenario runs carry bound/gap fields. | `OptimizeConfig.lp_bound` records `lp_bound`, `lp_gap`, and `lp_status`; validation and `scenario_runs.csv` carry the fields. | Met |
| `python scripts/dashboard.py` is green. | Lint, format, types, tests, validator, docs, and docstrings pass at the evidence head. | Met |

## 2. Workflow compliance

- Parent issue before the branch: #238 was created before `feature/p29-mip`.
- Branch from `main`: the worktree starts at `68a1140`, the P28 head.
- Commit messages start with task IDs: `P29.1`, `P29.2`, `P29.3`, and the documentation commit.
- Roadmap and changelog in step: P29.1 to P29.3 are checked; the changelog records each.
- Child issues are closed with closeout evidence: #239, #240, and #241.
- Approval gates: the phase opened no pull request until this report; it did not merge, tag, release,
  or change a setting.

## 3. Gate evidence

| Gate | Result at the evidence head |
| --- | --- |
| lint | green |
| format | green |
| types | green |
| tests | green, coverage at or above 90% |
| validator | green |
| docs | green |
| docstrings | green |

## 4. Behaviour smoke

On the two-block synthetic estate:

- `ws4 solve-mip`: status **optimal**, 2 variables, 2 blocks scheduled, option objective **0**,
  replayed target penalty **0**, spatial violations **0**.
- `scripts/exact_vs_heuristic.py`: exact status **optimal**, exact replayed penalty **0**,
  heuristic replayed penalty **0**, gap **0**. This is a bounded-model comparison on a tiny fixture,
  not evidence that either lane is optimal for the full spatial problem.
- `ws4 optimize --lp-bound`: `lp_bound` **0**, `lp_gap` **0**, `lp_status` **optimal**.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The exact lane is the option-selection model, not the full spatial model. | Green-up, core area, patch distribution, routes, and spread connectivity are not in that MIP. | Every `mip.json` and comparison report names the boundary. |
| `--limit-blocks` is diagnostic only. | The heuristic has no equivalent candidate subset. | The exact-vs-heuristic script does not use it; the MIP command labels it a subproblem. |
| LP/MIP gaps are only present when the opt-in flags are used. | The extra solves cost time. | Default runs are unchanged; the fields appear on request. |

## 6. Next phase

Goal: make the GBR dataset's provenance visible and the data-quality block pass.

Tasks:

- P30.1 Populate `manifest.metadata` for TSA 46 and TSA 47 with inventory vintage, imputation
  share, coverage, and curve provenance.
- P30.2 Make the P26 `data_quality` block report `ok` for both instances and keep `unknown` for
  genuinely missing fields.
- P30.3 Publish a model-limitations page covering VDYP transform, predecessor THLB, operability,
  markets, fire, and access.

Recommended defaults:

- The metadata is sourced from the FEMIC run artefacts and instance notes; no invented values.
- The limitations page is linked from both instance sites and the ws4 docs.
- A missing field stays a warning, not a pass.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
