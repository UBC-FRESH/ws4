# Phase close-out report: P27 Goal normalization and priority tiers

Phase: P27, Goal normalization and priority tiers
Parent issue: #227
Pull request: not opened yet
Evidence head: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-24
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge the P27 pull request, and delete the branch `feature/p27-normalization`.
2. Close parent issue #227 with a closeout comment that cites the merge commit.
3. Launch P28, Inventory and ending-inventory constraints: add ending-inventory targets and a
   non-declining-yield ceiling path, with report fields for both.

Settings changes: none. This phase changes no repository setting, tag, release, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A target can set `normalization: auto`; the normalized penalty and scale are reported. | `normalization_scale` and `raw_penalty`; `report_targets.csv` carries `raw_penalty`, `penalty`, `scale`, `normalization`, and `priority`. The MIP/LP option model uses the same scale. | Met |
| Targets with different `priority` values use the priority-aware objective; default targets do not. | `priority_total` uses a `1e9` step multiplier across tiers; target default one leaves the sum unchanged. The incremental evaluator and full objective agree on a mixed-priority fixture. | Met |
| Existing targets produce the same objective and report values. | Defaults are `normalization: none` and `priority: 1`; the existing report/objective tests pass unchanged, with additive columns. | Met |
| `python scripts/dashboard.py` is green. | Lint, format, types, tests, validator, docs, and docstrings pass at the evidence head. | Met |

## 2. Workflow compliance

- Parent issue before the branch: #227 was created before `feature/p27-normalization`.
- Branch from `main`: the worktree starts at `f9bdda8`, the P26 head.
- Commit messages start with task IDs: `P27.1-P27.2`, `P27.3`, and the documentation commit.
- Roadmap and changelog in step: P27.1 to P27.3 are checked; the changelog records each.
- Child issues are closed with closeout evidence: #228, #229, and #230.
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

On the synthetic two-block estate, a run with:

- `feature.Volume` minimum 500, `normalization: auto`, `priority: 1`
- `feature.Volume` maximum 300, `normalization: auto`, `priority: 2`

reported objective **1.3333**, `report_targets.csv` scales **500** and **300**, raw penalties
**0** and **400**, normalized penalties **0** and **1.3333**, and statuses **met/above**. The
higher-priority floor is satisfied, so the lower-priority excess is the active term. This is a
smoke result on the tiny fixture, not a production benchmark.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Priority is a large fixed multiplier, not a certified lexicographic solve. | The solvers consume one scalar; a true lexicographic comparator would require solver-level tuple support. | The report states the weighting and keeps every per-target term visible. |
| The auto scale uses the larger absolute bound. | A statistical scale would need a pilot distribution and would change with the seed. | The rule is deterministic, recorded, and opt-in; calibration remains separate. |
| The scenario comparison carries target fields but does not add a dedicated normalized-deviation column. | The target table already contains `raw_penalty`, `penalty`, `scale`, `normalization`, and `priority`. | Consumers can pivot on the columns; docs name them. |

## 6. Next phase

Goal: make inventory and flow ceilings explicit.

Tasks:

- P28.1 Add ending-inventory targets and report fields.
- P28.2 Add a non-declining-yield ceiling path with a clear feasibility/status report.
- P28.3 Compare ending inventory and flow ceilings across scenarios.

Recommended defaults:

- Ending inventory is a level target at the period end, not a new account type.
- A flow ceiling is advisory unless paired with a hard `reject`/`repair` policy.
- Keep the current weighted objective as the default.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
