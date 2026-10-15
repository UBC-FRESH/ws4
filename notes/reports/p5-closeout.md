# Phase close-out report: P5 Operate and maintain

Phase: P5 Operate and maintain
Parent issue: #44
Pull request: #51, `feature/p5-operate` into `main`
Evidence head: `880c14a`, the head that the gates and the CI runs below cover
Report commit: the commit that adds this report. Its CI run is posted on pull request #51.
Date: 2026-10-15
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #51, and delete the branch `feature/p5-operate`.
2. Close parent issue #44 with a closeout comment that cites the merge commit.
3. Set P5 to `complete` in `ROADMAP.md` (its task and subtask boxes are now checked).
4. Launch the performance and scalability build (P6): create its parent issue and its branch
   `feature/p6-performance`, create the WP0 to WP7 child issues as sub-issues, and start WP0 (the
   benchmark harness and baseline).

Settings changes, each with its exact command. Each one runs only after its own approval.

```bash
# Enable Dependabot security updates (alerts are already enabled).
gh api -X PUT repos/UBC-FRESH/ws4/automated-security-fixes
```

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A review cadence exists and the first review is recorded | `notes/review-cadence.md` (`f20fb79`) | met |
| Issue triage: labels, templates, and a triage cadence | `notes/triage.md`, `.github/pull_request_template.md`, the labels (`cf35356`) | met |
| Dependency and security maintenance has an automated, documented cadence | `.github/dependabot.yml`, `notes/dependencies.md` (`880c14a`) | met |
| The roadmap, backlog, and changelog stay in step on a cadence | `notes/sync-checklist.md` and the first sync (`880c14a`) | met |
| A release and patch policy exists | `notes/release-policy.md` (`880c14a`) | met |
| A maintainer and handover guide exists | `notes/handover.md` (`880c14a`) | met |
| `python scripts/dashboard.py` stays green | `OVERALL: GREEN` at `880c14a` | met |

## 2. Workflow compliance

- Parent issue before the branch: parent #44 was created before the branch `feature/p5-operate`.
- Branch from `main`: merge-base `9e4419d` (the post-release docs fix on `main`).
- Commit messages that start with task IDs: 4 of 4 (`8d50c5e` P5 activation, `f20fb79` P5.1,
  `cf35356` P5.2, `880c14a` P5.3-P5.6).
- Gates for each commit: section 3.
- Roadmap and changelog in step: updated with each task.
- Child issues closed with closeout evidence: #45, #46, #47, #48, #49, #50 are closed, each with a
  closeout comment that cites its commit.
- Approval gates: the branch, commits, pushes, issues, and the pull request are within the active
  phase. The one settings change (Dependabot security updates) is named above and waits for approval.

## 3. Gate evidence

| Commit | Gates | Result |
| --- | --- | --- |
| `8d50c5e` P5 activation through `880c14a` (4 commits) | `python scripts/dashboard.py` | `OVERALL: GREEN` at each commit |
| `880c14a` (evidence head) | `python scripts/dashboard.py` | `OVERALL: GREEN`; lint, format, strict types, 300 tests with the 90 percent coverage gate (94.28 percent), the workflow validator, and the docs build all pass |
| `880c14a` | `scripts/check_workflow.py` | `0 error(s), 0 warning(s)` |

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 38788461791 | `880c14a` | success | The pull request CI run (lint, format, types, tests, validator, docs). |

CI runs on pull requests and `main` only, so the branch commits before the pull request have no CI
run. The CI run for the report commit is posted on pull request #51.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Dependabot security updates are disabled at the repository level | They are a repository setting, not a file | Named as a settings change with its exact command above |
| P5.3 to P5.6 landed in a single commit | They are four small, independent documentation deliverables with no code interlock | One commit, `880c14a`, with the task IDs in the message; each issue closed separately with evidence |

## 6. Next phase

Phase 6: Performance and scalability build.

Goal: make the simulator, spatial metrics, and route model fast enough that the metaheuristic optimizer
can evaluate thousands of candidate schedules on a C5-class dataset within a practical budget, keeping
reproducibility and the compiled-dataset contract.

The plan of record is `notes/design/ws4-performance.md`. The child issues mirror its work packages:

- WP0 Benchmark harness and baseline (the prerequisite).
- WP1 Route and simulation quick wins.
- WP2 Vectorized simulator core.
- WP3 Spatial precompute and incremental metrics.
- WP4 Incremental objective evaluation.
- WP5 Solvers at scale (island model, batched evaluation, NUMA).
- WP6 Native kernels (numba, then optional C++).
- WP7 Guardrails (CI perf gate, parity and determinism tests, docs).

Acceptance criteria (from the plan):

- C5 30-year simulate under 1 s; 3-year simulate plus routing under 5 s.
- Patch accounts, edge contrast, and core area per year under 0.2 s.
- One optimizer objective evaluation on C5 under 50 ms (incremental).
- Near-linear scaling to 32+ cores; reproducibility preserved.

Recommended defaults, each with its reason:

- **Start with WP0 and WP1.** Reason: the harness makes every later gain measurable, and WP1 is the
  cheapest, largest win (route reconstruction and row-wise treatment application).
- **Prototype the incremental update (WP3/WP4 spike) before committing.** Reason: the delta approach
  is the biggest lever and the biggest risk.
- **Run the phase on the 72-core host.** Reason: WP5 and the profiling need it.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
