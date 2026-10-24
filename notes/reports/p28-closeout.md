# Phase close-out report: P28 Inventory and flow ceilings

Phase: P28, Inventory and flow ceilings
Parent issue: #233
Pull request: not opened yet
Evidence head: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-24
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge the P28 pull request, and delete the branch `feature/p28-inventory`.
2. Close parent issue #233 with a closeout comment that cites the merge commit.
3. Launch P29, MIP lane and exact small-instance validation: solve small instances to optimality,
   record the exact schedule and gap, and compare the heuristic result under a fair budget.

Settings changes: none. This phase changes no repository setting, tag, release, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| `report_targets.csv` names level and flow targets; `ending_inventory.csv` and a summary block report the final values. | `target_kind` adds `level`, `flow.even`, or `flow.ndy`; `ending_inventory` writes the final `feature.*` values and the summary carries the offset and account values. | Met |
| A max-flow probe can require NDY or even flow and reports the worst change and feasibility. | `max_flow --flow ndy|even` adds the flow target to each probe; probes record floor and flow feasibility and the worst percent change separately. | Met |
| Scenario comparison carries ending inventory and flow status. | `scenario_ending.csv` and `scenario_flows.csv` are written and named in the Markdown report. | Met |
| `python scripts/dashboard.py` is green. | Lint, format, types, tests, validator, docs, and docstrings pass at the evidence head. | Met |

## 2. Workflow compliance

- Parent issue before the branch: #233 was created before `feature/p28-inventory`.
- Branch from `main`: the worktree starts at `b8d94b1`, the P27 head.
- Commit messages start with task IDs: `P28.1`, `P28.2`, `P28.3`, and the documentation/refresh commits.
- Roadmap and changelog in step: P28.1 to P28.3 are checked; the changelog records each.
- Child issues are closed with closeout evidence: #234, #235, and #236.
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

- The synthetic optimizer run writes `ending_inventory.csv` and a summary block with the final
  `feature.Volume` value; `report_targets.csv` carries the target kind.
- A two-period NDY probe (`feature.Volume`, high 300, one probe) reported floor **true**, flow
  **true**, worst change **1.78571%**, per-period values **700 / 712.5**, and an advisory ceiling
  **150**. This validates orchestration on the tiny fixture, not a production AAC ceiling.
- Scenario comparison writes the ending and flow tables when the run artefacts are present and
  reports a missing constraint report as unavailable.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Closing inventory is not a new target type. | A `feature.*` level target at the final period already expresses it. | P28 labels and reports it rather than adding a redundant schema. |
| The flow ceiling remains advisory. | The high bound is additive and each probe is a finite search. | Floor and flow feasibility are reported separately; no certified maximum is claimed. |
| The flow probe uses a constant floor plus the flow band. | A full hard-flow MIP is a larger change. | The probe is a constructive ceiling and clearly labelled. |

## 6. Next phase

Goal: close the optimality gap loop on small instances.

Tasks:

- P29.1 Add a MIP lane that returns the exact schedule, objective, and status for a small
  dataset.
- P29.2 Add an exact-vs-heuristic comparison report under the same targets and budget.
- P29.3 Add the LP/MIP gap to the validation and scenario reports.

Recommended defaults:

- Keep the heuristics as the default for large instances.
- A MIP result is exact only for the configured option-selection model, not the full spatial
  problem.
- Report the gap honestly; do not call a bounded result optimal when the spatial rules are relaxed.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
