# Phase close-out report: P10 documentation and the API-first workflow

Phase: P10
Parent issue: #104
Branch: `feature/p10-docs-api`
Pull request: **#109**, stacked on `feature/p9-memory`
Head at close-out: `0b0c54c`
Report written: 2026-10-18

## Why the base is not `main`

Phase 9 is **held open** for its P9.5 export — an accounts export from a licensed Windows run — and
Phase 10 was branched from `feature/p9-memory` so that its work sat on the phase that produced the
context for it. A pull request against `main` would therefore carry Phase 9's ten unmerged commits as
well, and the approval would be about both phases at once. The stack keeps this pull request's diff to
Phase 10's own four commits. The base is one command away from changing (`gh pr edit 109 --base main`)
if landing both together is preferred.

## Recommendation

**Close P10.** The next phase is the backlog's capability work — succession and `produce` semantics,
legacy-ingestion coverage, account reports — unless the P9.5 export arrives first, in which case P9
closes first and this stack lands with it.

One thing to decide when P9 closes: with this stack, the merge order is P9 then P10, and Phase 9's
close-out report should say that its branch carries Phase 10's work.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A complete API-first session runs as a notebook in the gallery, executed, linked from the API pages | `examples/070_library_path.ipynb`, 15 cells, executed end to end, no `ws4` command anywhere; it simulates two schedules in memory, searches through `Optimizer.run`, reads results back as frames, and checks the run's numbers against a fresh simulation (largest difference **2.3e-13**) (`958bb7f`); linked from `docs/getting-started/python-api` and `docs/howto/automate-a-study`, and listed in `docs/examples.rst` | met |
| A documented command re-executes the notebooks and reports drifted output, and it can fail | `python scripts/check_notebooks.py`: **50 cells compared, 0 skipped, 0 drifted** across all eight notebooks, naming a notebook and cell when it differs and writing nothing; `--refresh` is the documented remedy; seven tests cover a current notebook, a stale one, a tagged cell, the normalisations, a notebook that no longer runs, the per-cell outcome, and the refresh (`26d9aad`) | met |
| Every example states whether it is a command-line session or a library one | all eight notebooks name their path in their opening paragraph, written from what their cells import and run; the gallery's intro explains the distinction and names `070_library_path` as the counterpart to `010_quickstart` (`958bb7f`) | met |
| The dashboard green at every commit, with the docs and docstrings gates | seven gates GREEN at the evidence head; `sphinx -W` builds the new gallery entry and the new API page clean. **One deviation**, recorded below: the launch commit landed red | met with a recorded deviation |

## 2. What shipped

**P10.1 (#105) an API-first walkthrough notebook.** The gallery had eight examples and five drove the
command line, so the library audience had prose (`getting-started/python-api`,
`howto/automate-a-study`) but no worked session. `070_library_path` is that session, and it closes by
mapping each step to the command that does the same thing, so the two paths are visibly one surface.

**P10.2 (#106) the gallery's outputs are checked.** `scripts/check_notebooks.py` re-runs every
notebook in memory and compares cell by cell with what is committed. It says what it cannot compare
rather than hiding it — the environment's version banner, durations, rates, memory and absolute paths
are normalised and **counted**, so a passing run prints
`duration x2, elapsed x2, memory x0, path x0, rate x2, version x10` — and a cell whose output is a live
render can be tagged `no-drift-check` in the notebook itself. Documented at
`docs/api/check-notebooks.rst`, in the API index, and on the gallery page.

**P10.3 (#107) every example says which way in it takes**, from what its cells actually import.

**P10.4 (#108) a bug the notebook found.** Its search cell reported `incumbent_objective 0.0` while
`report_targets.csv` said `below`. The report priced a periodic target from one year: the target's
period totals **5,549.86** where the report read the year-0 row alone, **1,627.14**, and charged a
penalty of 3,372.86 the search never applied. `target_status` now sums over `Target.cell_years()` —
the same expression the objective uses — with three tests, one of which asserts the report's total
penalty equals `objective`'s for the same values.

## 3. Gate evidence

`python scripts/dashboard.py`, at the evidence head:

| Gate | Status | Seconds |
| --- | --- | ---: |
| lint | GREEN | 0.08 |
| format | GREEN | 0.07 |
| types | GREEN | 0.74 |
| tests | GREEN | 51.21 |
| validator | GREEN | 0.28 |
| docs | GREEN | 3.16 |
| docstrings | GREEN | 2.32 |

The notebook check is deliberately **not** a gate: it takes **8 minutes** on this host against ~50
seconds for the whole dashboard, so it is a separate job in `ci.yml` (`Notebook outputs`) that installs
the `opt` extra and the notebook tooling.

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| (see the pull request) | `0b0c54c` | (see the pull request) | The first run of the `Notebook outputs` job: it had never run before this pull request. |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Flow targets in `report_targets.csv` are still mis-reported | `target_status` prices every target as a level target over its period, while the objective prices a `flow` target as a per-period percent series. Measured: an `ndy` target with `minimum: -1` over a series dropping 100 -> 60 is priced at **39.00** by the objective and reported as `met` with **0.00** | reported rather than guessed at, because fixing it means deciding what the report should *show* for a flow target (the period series, or the worst period); recorded in `notes/backlog.md` and in the roadmap's P10 section. Nothing shipped is affected: the sample estate's targets are level targets |
| The Phase 10 launch commit landed with the dashboard red | a roadmap tracker status I wrote said `active (held on the P9.5 export)` where the phase section says `active`, and the command chain ran on past the failing exit status | caught by the workflow validator on the next run and fixed by `0c44c5f`; the tracker row is back to `active`, the holding note is in the phase section, and the lesson (a chain hides an exit status) is in the changelog |
| The pull request is stacked rather than based on `main` | Phase 10 branched from `feature/p9-memory`, which is held open for P9.5 | stated in the roadmap, the changelog, the report and the pull request; one command changes the base |
| The `Notebook outputs` CI job has not run before this pull request | the job was added in this phase | it runs here, and its result belongs in this report before the merge |

## 6. Next phase

The backlog's capability work, in the order the backlog lists it: **succession and `produce`
semantics** (`partial`), **legacy-ingestion coverage** (`partial`), and **account reports**
(`partial`) — each a real capability with a measurable acceptance of its own, and none of them
release-blocking. The alternative, if the P9.5 export arrives first, is to close Phase 9 and land this
stack with it.

## 7. Decision

Awaiting the maintainer's approval to:

1. record the CI result in section 4;
2. close Phase 9 and this phase in order, or land this pull request on its own base;
3. squash-merge, delete `feature/p10-docs-api`, close #104 with a comment citing the merge commit, and
   launch the next phase.
