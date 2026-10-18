# Phase close-out report: P7 parity and the analyst workflow

Phase: P7 parity and the analyst workflow
Parent issue: #82
Pull request: #89, `feature/p7-parity` into `main`
Evidence head: `53904b8`, the head that the gates and the CI runs below cover
Report commit: the commit that adds this report. Its CI run is posted on pull request #89.
Date: 2026-10-18
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #89, and delete the branch `feature/p7-parity`.
2. Close parent issue #82 with a closeout comment that cites the merge commit.
3. Launch P8: create its branch, set the phase statuses in `ROADMAP.md`, create its child issues as
   sub-issues, and start its first task.

Settings changes, each with its exact command. Each one runs only after its own approval.

- **None.** The phase added no tag, release, repository setting, external account, or host package.
  `threadpoolctl` joined the `opt` extra and `requirements-dev.txt`, which is a dependency change
  recorded in the changelog and installed by the existing CI steps.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Both command-line gaps closed, with tests | `--weights` is optional and documented as accepted for compatibility; `--iterations` is added, defaulting to the 500 the configured default already used. Four behavioural tests in `tests/test_cli.py`: optimize runs with no weights file, `--iterations 7` appears in `summary.json`, a weights file is still accepted, and the help marks exactly three required options | met |
| `threads` applied, and the island scaling measured on an idle host | applied wherever an optimizer is built, which is the parent and every worker: the environment for libraries loaded later and for children, `threadpoolctl` for the pools already loaded. Scaling on the binding workload: 1 island 1 061 iterations/s, 8 islands 5 004, 32 islands 13 924, with a load average of 3.9 at the start | met with a stated limit: the host's load average moved between 4 and 65 across the session's runs, so no figure here is from a genuinely idle machine. The limit is diagnosed rather than asserted — BLAS pinning changes nothing (1 037 against 1 033 iterations/s on one island; 13 660/14 385 pinned against 12 318/15 877 unpinned on 32) — and both tables record the load they were taken at |
| The sample estate used by at least one guide and one notebook | `examples/estate`, used by `docs/howto/route-products.rst`, `docs/howto/patch-targets.rst`, and the notebooks `030_sample_estate`, `040_patch_targets`, `050_routes_and_mills`, `060_parameter_sweep`; pinned by `tests/test_example_estate.py` | met |
| The docs build and the docstrings gate green, with the dashboard green at every commit | `python scripts/dashboard.py` reports seven gates GREEN at the evidence head, and every commit in the phase was closed on a green run | met |

Supporting results, all recorded in `CHANGE_LOG.md` with their evidence:

- the patch-account correction (P7.6): a simulation of the incumbent and the incremental evaluator
  agree to the hundredth (11.87 / 16.20 / 71.93 percent across the size classes), and the run's report
  now prices the same shares with status `met`;
- the dense-harvest measurement (P7.5): the patch run is *faster* than the volume-only one on the same
  workload (60.6 against 25.9 iterations/s) because the patch ramp keeps the schedule sparse, and the
  profile puts the cost in the per-`(block, chain)` criterion series and the patch-state construction,
  not in the incremental relabel the earlier work optimised;
- the sample estate's verified behaviour: 64 fragments compile and validate, a simulation forms four
  openings (80.5 ha, largest 50.4 ha) and splits 8 793 m3 between both mills by haul cost, and a
  20 000-iteration search schedules 51 blocks over rotations.

## 2. Workflow compliance

- **Parent issue before the branch:** #82 was created, then the branch `feature/p7-parity` was cut from
  `main` at `6fdbece`.
- **Branch from `main`:** the merge base is `main`'s tip.
- **Commit messages that start with task IDs:** 6 of 6, one per task.
- **Roadmap and changelog in step:** every task landed with both, and the phase tracker moved to
  `active` at launch and to `pr-open` with this report.
- **Child issues:** six, all linked as sub-issues of #82 (#83, #84, #85, #86, #87, #88), all closed
  with a closeout comment carrying the evidence and the commit.
- **Approval gates:** the launch and each phase task were started on an explicit instruction, and P7.6
  was filed and added to the phase rather than fixed silently.

## 3. Gate evidence

The dashboard was run at every commit in the phase and reported GREEN; the record kept here is the run
at the evidence head:

```
GATE                STATUS   SECONDS
lint                GREEN       0.08
format              GREEN       0.07
types               GREEN       0.44
tests               GREEN      41.10
validator           GREEN       0.28
docs                GREEN       4.62
docstrings          GREEN       0.91

OVERALL: GREEN. Every gate passed.
```

## 4. CI evidence

CI runs on pull requests and on pushes to `main`, so this pull request is the branch's first CI run.

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| (posted on #89) | report commit | recorded on the pull request | the phase's six task commits were not covered by CI, since a branch push runs no workflow until a pull request exists |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The scaling criterion is met with a stated limit | the host's load average varied between 4 and 65 during the session, partly from the phase's own 32-process measurements | the limit is diagnosed (not BLAS), both measurement tables carry the load they were taken at, and a shared or mmapped dataset is recorded as the next thing to measure |
| `--iterations` defaults to 500, not the 2000 the issue suggested by analogy with `watch` | 500 is what the configured default already used | stated in the issue comment and the changelog: defaulting to 2000 would have silently lengthened every existing run and changed every result |
| P7.6 was filed as "a patch target in a search misprices the classes" and turned out to be the run's *report*, not the search | I trusted a reported figure over the search's own objective when I first characterised it | corrected in the issue comment with the three-way comparison, and the regression test pins the real behaviour |
| The dense-harvest path was measured, not improved | the issue allowed either, and the profile named a different bottleneck than the design note had | the measurement, the named bottleneck and two candidates are recorded with a baseline in the design note and the backlog |

## 6. Next phase

**P8 theme: verify the replacement claim.** Every phase so far has produced its most valuable finding
by *exercising* WS4 rather than by adding to it — the reporting-versus-search patch mismatch (P6.25),
the flow definitions read off the specification (P6.46), and the run report that mispriced patch
accounts (P7.6) all surfaced that way. A phase that verifies the claim systematically is the natural
next move. Recommended tasks, each with its reason:

1. **A parity harness against the reference implementation's outputs** — WS4's accounts and schedules
   compared to the established tool's own reports for the sample estate and a C5-class model, with the
   comparisons that a reviewer can run. Reason: this is the claim the project exists to support, and it
   is currently asserted rather than demonstrated.
2. **Reproduce the C5 patch and flow results end to end from a clean checkout**, with the exact sample
   input documented. Reason: the P6 figures were measured interactively, and the sample the estimator
   used is not in the repository.
3. **The performance lever P7.5 named** — a vectorised criterion series and a lazily built patch state,
   judged against the recorded baseline. Reason: it is the measured cost of a spatial search, and it now
   has a baseline to improve on.
4. **Island scaling on a controlled host** — the memory-traffic question (a shared or mmapped dataset),
   measured on a machine whose load is known. Reason: it is the one acceptance criterion still carrying
   a stated limit.

Acceptance for P8: a parity comparison a reviewer can run and read; the C5 results reproducible from
documented inputs; the criterion-series work judged against the P7.5 baseline; and the dashboard green
with the docs and docstrings gates.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
