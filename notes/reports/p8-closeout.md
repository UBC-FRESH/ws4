# Phase close-out report: P8 verify the replacement claim

Phase: P8 verify the replacement claim
Parent issue: #90
Pull request: #96, `feature/p8-verify` into `main`
Evidence head: `5f282ee`, the head the gates cover, plus the commits that queue this report
Report commit: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-18
Status: queued for approval. Not merged.

## Why the phase closes with a task carried forward

Phase 8's own acceptance criteria — the four below — are met. P8.5 was added mid-phase, on approval,
after P8.1 established the gap it closes, and it is **blocked on an input from outside this repository**:
producing a reference account report needs a licensed Windows run. Holding the phase open for it would
leave this phase's nine commits unmerged and rebasing against a moving `main` for however long that
takes, which is the opposite of what the deferred-work mechanism is for.

So #95 is deferred to Phase 9 with its state intact — the comparison is built, tested and documented,
the sample it runs on is packaged with digests, and only the reference's export is missing — and it is
re-linked as a sub-issue of the next phase's parent at that launch. The report's section 6 folds it
back in as a P9 task, so nothing is lost but the artificial coupling of a ready phase to a Monday.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #96 and delete `feature/p8-verify`.
2. Move #95 to be a sub-issue of the next phase's parent, keeping it open, and close parent issue #90
   with a closeout comment that cites the merge commit.
3. Launch P9 (see section 6) and start its first task.

Settings changes: **none**. No tag, release, repository setting, external account, or host package was
involved in this phase. (`pypandoc-binary` was installed in an earlier phase's session for the docs
build; nothing was installed for Phase 8.)

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A parity comparison a reviewer can run and read, with the differences it found either fixed or explained | `scripts/acceptance.py --roads-sample <sample>/roads`: WS4's least-haul-cost routes compared node by node against the reference's own `cost_destination.<mill>.csv`, **no differences in 37,701 comparisons** (`38d30f5`); the method, the tolerances and what it does *not* cover are in `notes/design/ws4-parity-harness.md` | met |
| The C5 patch and flow results reproducible from inputs documented in the repository | `docs/reference/performance.rst` names what the sample must contain, gives the three invocations verbatim, and separates portable counts from host-dependent timings; the re-run reproduces 16,174 fragments exactly and every timing within the noise of a shared host (`59f9bbb`), recorded in `notes/performance.md` | met, with the sample's absence from the repository stated and mitigated by packaging it |
| The criterion-series work judged against the P7.5 baseline, with the measurement recorded | 58.6 → 41.5 µs per call (−29%) on a stashed/unstashed A/B on the same machine, the C5 patch-ramp workload 60.6 → 73.3 iterations/s (+21%), identical results (53 tests, the routing parity, and the series values for no treatment, one cut and two cuts) (`e263f10`, `c29109b`) | met |
| Island scaling measured with the host's load recorded, and the memory-traffic question answered | 1 / 4 / 8 / 16 / 18 / 32 islands at loads 5–13: 1,055 → 3,238 → 6,014 → 9,432 → 11,782 → **18,685 iterations/s (17.7× at 55%)**; efficiency is ~56% at 16 islands on 36 physical cores, which rules out BLAS, the per-process setup and SMT by measurement, leaving the memory hierarchy (`dd2ddbb`) | met with a stated limit whose cause is measured |
| The dashboard green at every commit, with the docs and docstrings gates | seven gates GREEN at the evidence head; **one deviation**: the first P8.3 commit landed with the format gate red because the commit was chained onto a `tail` rather than the dashboard's exit status, fixed by the follow-up `c29109b` | met with a recorded deviation |
| (added mid-phase, deferred) Compare WS4's accounts against a reference report | the `accounts` check, the export specification and the packaged, digest-pinned sample (`4fcecb0`, `2de2323`, `7ef5ecf`); the comparison has not run because its input is a reference export from a licensed Windows run | **deferred to P9**, carried as task 5 there |

Supporting results:

- **The routing parity**: 36,722 segments, 27,231 vertices, three mills, 12,568 blocks — WS4 agrees with
  the reference on all 37,701 node-and-mill pairs a block links to, including every node the reference
  marks unreachable.
- **The C5 reproduction**: 30-year `simulate` 0.113 s against 0.108 recorded; 3-year `simulate` with
  routing 0.576 s against 0.685; patch accounts 28 ms per year against 29; edge contrast 1.147–1.251 s
  against 1.157; peak memory 487–504 MB against 496; fragments 16,174 exactly.
- **The scaling cause**, with the three alternatives excluded by measurement: BLAS pinning is neutral
  (P7.2), the per-process setup is ~1 s against 4–7 s of search, and 16 processes on 36 physical cores
  share no SMT siblings while each holds about one core.
- **A finding for the next experiment**: the simulator writes to the fragments frame it inherits
  (`self.fragments["offset"] = ...`), so a forked worker's copy-on-write pages are copied anyway and a
  shared or mmapped dataset needs a read-only simulation state to help.

## 2. Workflow compliance

- **Parent issue before the branch:** #90 was created, then `feature/p8-verify` was cut from `main` at
  `6fdbece`.
- **Branch from `main`:** the merge base is `main`'s tip.
- **Commit messages that start with task IDs:** 8 of 8.
- **Roadmap and changelog in step:** every task landed with both; the tracker and the section are
  `active` and move together at close-out.
- **Child issues:** five, all linked as sub-issues of #90 (#91–#95), four closed with closeout comments
  carrying the evidence.
- **Approval gates:** the launch and each task were started on an explicit instruction; P8.5 was added
  mid-phase on an explicit instruction after P8.1 established the gap it closes; the close-out is not
  being opened early.

## 3. Gate evidence

The dashboard was run at each task's end and reports GREEN at the evidence head:

```
GATE                STATUS   SECONDS
lint                GREEN       0.08
format              GREEN       0.07
types               GREEN       1.03
tests               GREEN      40.56
validator           GREEN       0.27
docs                GREEN       4.13
docstrings          GREEN       0.87

OVERALL: GREEN. Every gate passed.
```

## 4. CI evidence

CI runs on pull requests and on pushes to `main`, so this branch is uncovered until its close-out opens
a pull request — the same shape as the previous phases.

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 39089975716 | `11a10a6` | success | the phase's first run, and green on it: Quality gates, Green dashboard summary, Pre-commit parity. The two traps that failed earlier phases' first runs were pre-empted — no shell magics in the notebooks, no assertion on terminal-wrapped help text — and the acceptance change was covered by tests before it was pushed. |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The first P8.3 commit landed with the format gate red | the commit was chained onto a `tail` of the dashboard output instead of its exit status — the same mistake as an earlier `sphinx -W` check in this project | fixed by the follow-up `c29109b`; the dashboard is green and the lesson (check the exit code, not the tail) is recorded in the issue comment |
| The C5 sample is not in the repository, and the newest installer cannot be extracted here | the sample ships inside a lab installer; the 2026-07-29 build is a protected or non-standard Inno build that neither `innoextract` 1.9 nor its development release reads ("unexpected setup loader revision: 2", checksum mismatch) | the extracted 2019 sample is used, and it is packaged in the workspace's untracked `tmp/` with a digest for all 139 files, so a copy can be verified rather than assumed |
| The accounts-parity claim remains unverified | the reference sample ships no account report, and producing one needs a licensed Windows run | P8.5 built the comparison, specified the export and packaged the sample, and is **deferred to P9** rather than holding this phase open; the comparison runs when the export arrives |
| P8.4 answers the memory question by measurement and reasoning rather than by a shared-dataset change | the change needs a read-only simulation state, which the phase did not have room for | the finding is recorded with the reason, so the next attempt starts from evidence rather than a hypothesis |

## 6. Next phase

**P9 theme: spatial performance and memory.** Phase 8 established where the cost is and, for the first
time, *why*; Phase 9 acts on it. Recommended tasks, each with its reason:

1. **A read-only simulation state, so a shared or mmapped dataset can help.** Reason: P8.4 measured the
   scaling limit as memory and found that the simulator's per-run write to the inherited fragments frame
   defeats copy-on-write, so this is the prerequisite for the obvious fix.
2. **Re-measure island scaling once the dataset can be shared**, on a host whose load is recorded.
   Reason: the criterion is currently met at 55% efficiency, with a measured cause; this is the test of
   whether that cause is the fixable one.
3. **The patch-state construction**, ~48 ms per state, now the largest single item in a spatial run's
   setup. Reason: P8.3 took the criterion series; this is what is left of the profile.
4. **`CurveTable.gather`'s per-call `np.clip`** (an `iinfo` per call, ~1.5 µs). Reason: small but on
   every curve evaluation in every simulation, and identified by the same profile.
5. **The accounts comparison's result, folded back**, whatever it shows. Reason: differences it finds
   are either fixes or documented limits of the replacement claim.

Acceptance for P9: a measurable improvement to spatial scaling or a measured reason there is none; the
patch-state and curve-gather costs judged against the P8.3 profile; and the dashboard green with the
docs and docstrings gates.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
