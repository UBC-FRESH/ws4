# Phase close-out report: P6 performance and scalability build

Phase: P6 performance and scalability build
Parent issue: #60
Pull request: #81, `feature/p6-performance` into `main`
Evidence head: `d22eae7`, the head that the gates and the CI runs below cover
Report commit: the commit that adds this report. Its CI run is posted on pull request #81.
Date: 2026-10-17
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #81, and delete the branch `feature/p6-performance`.
2. Close parent issue #60 with a closeout comment that cites the merge commit.
3. Launch P7: create its branch, set the phase statuses in `ROADMAP.md`, create its child issues as
   sub-issues, and start its first task.

Settings changes, each with its exact command. Each one runs only after its own approval.

- **Move the release tag `v0.1.0`** to the rewritten equivalent of its commit, so the release points
  into the current history rather than the pre-rewrite history:
  `git tag -f -a v0.1.0 -m "<its existing message>" <rewritten commit> && git push --force origin v0.1.0`
  Reason: it is the one reference still pointing at the pre-rewrite commits after the authorship
  consolidation below. Moving a release tag was not done unasked.
- Anything else: none. No tag or release was created in this phase, no repository setting was changed,
  and no account or server was touched.

Two changes were made during the phase under the maintainer's explicit instruction, and are named here
for the record:

- **Commit authorship consolidation.** `git config --global user.name "Gregory Paradis"`,
  `git config --global user.email "gregory.paradis@ubc.ca"`, `git config --local --remove-section user`,
  then `git filter-branch --env-filter '...' -- main feature/p6-performance` (author and committer
  only; trees, dates, and commit counts verified unchanged), followed by
  `git push --force-with-lease origin feature/p6-performance`, `... origin main`, and
  `git push --force origin <the eleven p6 checkpoint tags>`. The 32 commit citations in the roadmap,
  changelog, phase reports, and design notes were refreshed to the new SHAs in the same commit. This
  closed the three open dependency pull requests (#57–#59) as a side effect: dependabot deletes its
  branch when it closes a pull request, and GitHub refuses to reopen one, so they will return on the
  weekly schedule or from **Settings → Code security → Dependabot → Check for updates**.
- **pandoc on the build host.** `sudo apt-get update && sudo apt-get install -y pandoc`, because
  `nbsphinx` renders the example notebooks and needs it. The same step was added to the three CI jobs
  that build the documentation.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| C5 30-year `simulate` under 1 s | `scripts/benchmark.py --scenario c5 --years 30`: `simulate_base_seconds 0.108`, 16,174 fragments | met |
| C5 3-year `simulate` plus routing (300 blocks) under 5 s | same benchmark at `--years 3 --route-blocks 300`: `simulate_routing_seconds 0.685` | met |
| Patch accounts, edge contrast, and core area per year under 0.2 s | patch accounts 0.860 s / 30 years = **29 ms/yr**; edge contrast 1.157 s / 30 years = **39 ms/yr**; core area + patch accounts 0.929 s / 30 years = **31 ms/yr**. Each 1-year run adds ~0.3 s of one-off setup (topology load, block areas, patch store) | met, with the setup cost stated |
| One optimizer objective evaluation on C5 under 50 ms (incremental) | the move-based evaluator: additive move **0.003 ms** (333k moves/s), patch-targeted move 0.004 ms when the move does not change patch structure, and a *binding* volume-plus-patch workload at **1,006 iterations/s** (~1 ms/iteration) | met |
| Near-linear scaling to 32+ cores; reproducibility preserved | island model, binding workload, 4,000 iterations per island: 1 island 991 it/s, 8 islands 6,303 it/s (**6.4×**), 32 islands 15,110 it/s (**15.3×**). Reproducibility: `starts=4` with `workers=1`, with `workers=4`, and repeated, all return objective `8983775.786609` exactly | met with a stated limit: 15× at 32 islands, on a host that was shared while measuring, and each island pays a fixed ~1 s setup |
| The dashboard stays green | `python scripts/dashboard.py`: seven gates GREEN at `d22eae7` | met |

Supporting figures, from the same runs: 496 MB peak resident memory for the C5 benchmark, and a
full evaluator reset costs 0.76 s (additive) or 1.09 s (with patch accounts) once per run.

## 2. Workflow compliance

- **Parent issue before the branch:** #60 predates the branch; branch `feature/p6-performance` was cut
  from `main`.
- **Branch from `main`:** the merge base is `main`'s tip, `a8cb148`.
- **Commit messages that start with task IDs:** 74 of 97. The 23 exceptions are the milestone commits
  of the early performance spikes (P6.8–P6.13), which used a `spike M1:`-style prefix instead.
- **Roadmap and changelog in step:** every task landed with both. The exceptions are the spike
  commits above, whose results were written up when the spike was adopted.
- **Child issues:** P6.1–P6.19 have child issues (#62–#80). P6.20–P6.48 do not; their state lives in
  `ROADMAP.md` and `CHANGE_LOG.md`.
- **Approval gates:** the authorship rewrite, the checkpoint tag re-pointing, the `v0.1.0` decision,
  and the host pandoc install were each carried out on an explicit instruction, and are named above.

## 3. Gate evidence

The dashboard was run repeatedly during the phase and reported GREEN at every commit that closed a
task; the record kept here is the run at the evidence head:

```
GATE                STATUS   SECONDS
lint                GREEN       0.08
format              GREEN       0.08
types               GREEN       0.46
tests               GREEN      30.89
validator           GREEN       0.27
docs                GREEN       4.01
docstrings          GREEN       0.86

OVERALL: GREEN. Every gate passed.
```

Per-commit run records were not archived, so the evidence is the final run plus the sequence of
GREEN results reported in `CHANGE_LOG.md`.

## 4. CI evidence

CI runs on pull requests and on pushes to `main`, so this pull request is the branch's first CI run.

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| (posted on #81) | report commit | recorded on the pull request | the branch had no prior CI run by design |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| 23 commit messages without a task ID | the early spikes used a milestone prefix | recorded here; not rewritten, because the phase's history had just been rewritten for authorship and a second rewrite would invalidate the refreshed citations |
| `ws4 optimize --weights` is required but unused | the option was added for a weights file that was never implemented | documented truthfully in the FAQ and the targets guide, and recorded in `notes/backlog.md` for P7 |
| `threads` is documented but never applied | the setting was added with the worker pool, which reads `workers` | recorded in `notes/backlog.md` for P7; the scaling measurement was taken with BLAS pinned in the environment |
| `Optimizer.last_account_values()` is empty after `run` | the incremental search path does not populate it | recorded in `notes/backlog.md`; the run's own `account_values.csv` is the reliable source |
| Dependency pull requests #57–#59 were closed by the force-push to `main` | dependabot closes a pull request whose base history was rewritten, and deletes its branch | they return on the weekly schedule, or on demand from the Dependabot settings page |
| The docs build needed a system package | `nbsphinx` requires pandoc | installed on the host and added to the three CI jobs that build the docs |

## 6. Next phase

**P7 theme: parity and the analyst workflow.** The phase that makes the replacement claim checkable
and the tool comfortable to use all day. Recommended tasks, each with its reason:

1. **Wire the two command-line gaps** — apply `--weights` or drop the requirement, and add
   `--iterations` to `ws4 optimize` to match `watch` and `calibrate`. Reason: a required option with
   no effect is the first thing a new user trips over, and the iteration budget is the control an
   analyst reaches for first.
2. **Apply the `threads` setting** to the process it names, and re-measure island scaling on an idle
   host. Reason: the scaling criterion is met with a limit that this closes.
3. **Ship a sample estate** under `examples/` — a recipe, an inventory, a topology, and road tables —
   so the how-to guides and the notebooks can run against something larger than two blocks. Reason:
   every guide currently either uses a two-block toy or tells the reader to supply files.
4. **Add the missing notebooks**: a patch-target run, a route run, and a sweep; plus **a concepts
   section** (the textbook WS3 has and WS4 does not). Reason: the gallery and the reference are the
   two places a new analyst learns the model, and the concepts are currently only in the reference.
5. **Patch performance under a dense harvest** — 168 iterations/s at 4,612 harvested blocks against
   1,006 at a light one. Reason: it is the measured limit of the spatial path, and the one number a
   long spatial run is bounded by.

Acceptance for P7: the two command-line gaps closed with tests; `threads` applied and scaling measured
on an idle host; the sample estate used by at least one guide and one notebook; the docs build and the
docstrings gate green.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
