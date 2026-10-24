# Phase close-out report: P24 Search portfolio and multi-objective

Phase: P24, Search portfolio and multi-objective
Parent issue: #207
Pull request: not opened yet
Evidence head: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-24
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge the P24 pull request, and delete the branch `feature/p24-search-portfolio`.
2. Close parent issue #207 with a closeout comment that cites the merge commit.
3. Launch P25, Constraint repair and flow ceilings: the repair strategy, the binary-search
   max-flow engine, and the constraint-strategy report.

Settings changes: none. This phase changes no repository setting, tag, release, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| An archive keeps nondominated elites under named max/min metrics and exports schedules. | `ws4.opt.archive` with `Elite`, `EliteArchive`, `dominates`, and `pareto_front`; `archive.json` plus one schedule CSV per elite. Tests cover dominance, ties, replacement, capacity, and export. | Met |
| A portfolio run varies target weights, records every member, and writes a front table. | `ws4.opt.portfolio` and `scripts/portfolio.py`; weight factors scale matching target weights, every member records its seed/objective/metrics, and the output is `portfolio.json`, `portfolio.md`, `front.csv`, and `archive/`. | Met |
| A tuner run ranks configurations by a stated budget and seed set. | `ws4.opt.tune` and `scripts/tune.py`; grid and seeded-random modes, best/median ranking, `tuning.json`, `tuning.md`, and `best.json`. | Met |
| The LP relaxation reports finite target duals and option reduced costs on a small instance. | `solve_lp` and `relaxation_for` share the option-selection program with `solve_mip`; `scripts/lp_sensitivity.py` writes JSON and Markdown. The synthetic smoke reports a binding floor dual of 1.0 and CC reduced costs 360/340. | Met |
| `python scripts/dashboard.py` is green. | Lint, format, types, tests, validator, docs, and docstrings pass at the evidence head. | Met |

## 2. Workflow compliance

- Parent issue before the branch: #207 was created before `feature/p24-search-portfolio`.
- Branch from `main`: the worktree starts at `3c6ae67`, the P22/notebook-fix head.
- P23 was already active for accounts and target activation (#206), so this work took the next free
  phase identifier, P24, rather than colliding with that branch.
- Commit messages start with task IDs: `P24.1`, `P24.2`, `P24.3`, `P24.4`.
- Gates for each commit: the dashboard is green at the evidence head.
- Roadmap and changelog in step: P24.1 to P24.4 are checked; the changelog records each.
- Child issues are closed with closeout evidence: #208, #209, #210, and #211.
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

## 4. End-to-end smoke

The new commands ran on the synthetic estate (`examples/synthetic`) with a two-block compiled
dataset:

- Portfolio: 3 weight factors × 2 seeds = 6 members, all zero-penalty on the 500 m3 ceiling; the
  exact metric tie kept one seed on the front. The report, front CSV, and archive were written.
- Tuner: 2 × 2 temperature/cooling grid × 2 seeds = 8 runs; all zero-penalty, so the deterministic
  label tie-break chose `candidate-000`. The report and `best.json` were written.
- LP: an impossible 1000 m3 floor was binding with dual 1.0 and zero slack; the two CC options had
  reduced costs 360 and 340. This is the expected direction: forcing an option that lowers volume
  worsens a volume-floor penalty.

These are smoke results on a tiny fixture, not production benchmarks.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The phase identifier is P24, not P23. | P23 was opened concurrently as "Accounts and target activation" (#206). | Used the next free identifier and kept the work in a separate worktree. |
| The tuner implements grid and seeded random only. | Bayesian optimization needs a surrogate and a larger evaluation budget; it is a separate decision. | Recorded as a follow-up; the tuner's space and ranking are reusable. |
| The LP is a relaxation and the CLI takes an optional block subset. | A full landscape is much larger than the intended subproblem, and a relaxation is not a schedule. | `--limit-blocks` declares the subset and every report labels the result advisory. |
| Portfolio front members are finite grid points. | The portfolio is a budgeted sample over weight vectors and seeds. | The docs and report state that the front is not a certified optimum. |

## 6. Next phase

Goal: make hard feasibility explicit and fast to test.

Tasks:

- P25.1 Add `--constraint-strategy reject|penalize|repair` with per-strategy counts.
- P25.2 Add a binary-search max-flow engine that finds the highest feasible even-flow level and
  can warm-start SA.
- P25.3 Add a constraint-strategy/feasibility block to the run summary and report.

Recommended defaults:

- Keep penalize as the default; reject and repair are opt-in.
- Treat the max-flow level as a constructive ceiling, not a certified AAC.
- Record every repair in telemetry so a plan review can audit it.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
