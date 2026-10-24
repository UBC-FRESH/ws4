# Phase close-out report: P25 Constraint repair and flow ceilings

Phase: P25, Constraint repair and flow ceilings
Parent issue: #214
Pull request: not opened yet
Evidence head: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-24
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge the P25 pull request, and delete the branch `feature/p25-constraints`.
2. Close parent issue #214 with a closeout comment that cites the merge commit.
3. Launch P26, Reproducibility and data quality: a complete run manifest, a data-quality
   block, and the scenario-comparison report.

Settings changes: none. This phase changes no repository setting, tag, release, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| `reject` and `repair` produce zero spatial violations on a constrained fixture. | `ConstraintGuard` wraps every operator; the synthetic run with a 4 ha opening cap reported zero final violations for both policies. Tests cover reject, repair, and initial-seed repair. | Met |
| `penalize` behavior is unchanged, and an unknown strategy fails before the search. | The guard is disabled for `penalize`; `OptimizeConfig` validates the three values. Existing penalty tests remain green. | Met |
| The summary records the strategy, counts, and final feasibility. | `summary.json` contains `constraint_strategy`, `constraint_stats`, and `constraint_feasible`; `constraint_report.json` carries the final violation records. | Met |
| `scripts/max_flow.py` writes the ceiling, probe log, and best feasible schedule. | The script writes `max_flow.json`, `max_flow.md`, `probe-config.json`, the probe run directories, and `best-schedule.csv`. A zero-ceiling case writes an empty schedule, not a crash. | Met |
| `python scripts/dashboard.py` is green. | Lint, format, types, tests, validator, docs, and docstrings pass at the evidence head. | Met |

## 2. Workflow compliance

- Parent issue before the branch: #214 was created before `feature/p25-constraints`.
- Branch from `main`: the worktree starts at `cd7c216`, the P24 head.
- P23 remains a separate unmerged branch for accounts and target activation (#206); this phase did
  not touch it.
- Commit messages start with task IDs: `P25.1-P25.2` and `P25.3`.
- Gates for each commit: the dashboard is green at the evidence head.
- Roadmap and changelog in step: P25.1 to P25.3 are checked; the changelog records each.
- Child issues are closed with closeout evidence: #215, #216, and #217.
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

## 4. Synthetic smoke

On the two-block synthetic estate with a 4 ha opening cap:

- Reject: 22 proposed, 13 feasible, 9 rejected, 0 repaired; final `constraint_feasible` true and
  `constraint_report.json` violations empty.
- Repair: the same counts on this seed; the direct guard test exercises the repair path by dropping
  one addition from a swap and keeping a feasible single-block remainder.
- Max flow: `feature.Volume`, one 1-year period, high 400, three probes → advisory ceiling 350,
  all probe values 700, best schedule written. This validates orchestration on a tiny fixture; it is
  not a production AAC ceiling.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| `reject` and `repair` evaluate the full schedule per proposal. | The exact hard check needs the current opening, green-up, and core state. | Opt-in only; `penalize` remains the scalable default. The docs say to use the hard policies on a constrained subproblem. |
| Repair is a one-block local heuristic. | A full constraint-repair model would duplicate the spatial simulator. | It tries dropping one addition, restoring one removal, or restoring one modification, then rejects. Every repair is counted separately. |
| Process-pool runs report `constraint_stats.available = false`. | Worker move counts are not aggregated into the parent summary. | The serial path records every count; a pool run still writes final feasibility from the replayed schedule. |
| The max-flow high bound is additive. | An exact flow ceiling would need a hard-flow MIP. | The high bound is labelled as an envelope, and the reported ceiling is the best verified probe. |

## 6. Next phase

Goal: make a run reproducible and its data limitations visible.

Tasks:

- P26.1 Add a run manifest with the code revision, dataset reference and hashes, full
  configuration, seed set, and environment.
- P26.2 Add a data-quality block: inventory vintage, imputation share, coverage gaps, and the
  model limitations that affect the AAC.
- P26.3 Add a scenario-comparison report over the same landscape with different targets or
  constraints, reusing the P24 archive and front.

Recommended defaults:

- The manifest is always written; the data-quality block is present even when a field is unknown.
- Scenario comparison is a report, not a new optimizer run type.
- Do not present a heuristic ceiling as a certified AAC.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
