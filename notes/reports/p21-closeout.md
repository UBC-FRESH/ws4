# Phase close-out report: P21 Search quality and validation

Phase: P21, Search quality and validation
Parent issue: #190
Pull request: not opened yet
Evidence head: `37c16e6`
Report commit: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-24
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge the P21 pull request, and delete the branch `feature/p21-search-quality`.
2. Close parent issue #190 with a closeout comment that cites the merge commit.
3. Launch P22, Map operations: pre-warm the durable tile cache, record a reverse-proxy deployment
   check under a path prefix, and add a memory profile for the 1M-fragment cold build.

Settings changes: none. This phase changes no repository setting, tag, release, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| `--reversion N` resets the current solution to the best every N accepted moves. | `solve_sa`, `solve_sa_delta`, `solve_tabu`, and `solve_ils` reset to the incumbent via `reversion_due`; a run records `reversion` in `summary.json`. Tests: `test_reversion_is_due_on_the_configured_interval`, `test_reversion_is_a_non_negative_accepted_move_count`, `test_a_run_records_its_reversion_interval`. | Met |
| The validation harness reports the distribution and the MIP gap. | `scripts/validate_search.py` runs SA, tabu, and ILS over seeds and writes JSON/Markdown. Tests: parsing, statistics, the sweep, unknown-engine rejection, Markdown, CLI output. A TSA 47 50-iteration SA/tabu sweep produced the table in `notes/reference/search-quality-validation.md`. | Met |
| The sensitivity report names binding targets, slack, and the marginal effect. | `scripts/sensitivity.py` reads `report_targets.csv` and the target file; reports shortfall, excess, nearest-bound slack, binding, and the per-unit objective weight. Tests: 4. A TSA 47 run shows ten missed targets with marginal 1.0. | Met, with the stated limit below |
| The threshold engine shares the existing operators and evaluator. | `solve_threshold` uses `Problem.registry` and `Problem.evaluate`; `--engine threshold --threshold N --cooling F` selects it. Tests: parameter guard, optimizer run, unknown-engine rejection. | Met |
| `python scripts/dashboard.py` is green. | Lint, format, types, tests (700), validator, docs, and docstrings pass at `37c16e6`. | Met |

## 2. Workflow compliance

- Parent issue before the branch: #190 was created before `feature/p21-search-quality`.
- Branch from `main`: the branch starts at the P20 squash merge `2123252`.
- Commit messages start with task IDs: `P21.1`, `P21.2`, `P21.3`, `P21.4`.
- Gates for each commit: the dashboard is green at the evidence head; the P21 commits were tested
  locally before each commit.
- Roadmap and changelog in step: P21.1 to P21.4 are checked; the changelog records each.
- Child issues closed with closeout evidence: #191, #192, #193, and #194.
- Approval gates: the phase opened no pull request until this report; it did not merge, tag, release,
  or change a setting.

## 3. Gate evidence

| Gate | Result at `37c16e6` |
| --- | --- |
| lint | green |
| format | green |
| types | green |
| tests | green (700 passed; coverage above the 90 percent gate) |
| validator | green |
| docs | green |
| docstrings | green |

## 4. CI evidence

The pull request is opened with this report. Its first CI run is posted on the pull request.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| `tests/test_web.py::test_the_tile_endpoint_returns_mvt_features` failed once during a dashboard run. | It passed in three isolated runs and two full-suite reruns; the failure was a transient tile decode under load, not a P21 change. | Reran the full suite and dashboard; both green. Recorded here rather than hidden. |
| The sensitivity report is not an LP dual/reduced-cost solve. | It reads the goal-programming target report; the MIP module returns a bound and gap, not duals. | The report names the limit. True LP dual sensitivity is a follow-up, not a claim of this phase. |
| The validation sweep example uses 50 iterations. | A production budget would take much longer; the point was to exercise the harness. | The note labels it a harness demonstration, not a benchmark claim. |

## 6. Next phase

Goal: keep the production map operationally fast and deployable on a shared host.

Tasks:

- P22.1 Pre-warm the durable tile cache for a model tree.
- P22.2 Record a reverse-proxy deployment check under a path prefix.
- P22.3 Add a memory profile for the 1M-fragment cold build and decide the cache/index budget.

Recommended defaults:

- Keep the current LOD policy: treated centroids below zoom 10, polygons at 10+.
- Keep the durable cache opt-in via `--tile-cache`.
- Treat the 29.3 s cold build as a pre-warm step, not a user-facing request.

The search portfolio (Pareto/multi-objective, tuners, LP dual sensitivity) follows as P23.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
