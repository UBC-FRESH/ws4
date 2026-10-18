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
| `39104469800` | `9bcdcfd` | **success** | All four jobs green: **Quality gates**, **Green dashboard summary**, **Pre-commit parity**, and **Notebook outputs** — the last being this phase's new job, and this phase's pull request being its first. |
| `39103477447` | `95ff5f3` | failure | Only `Notebook outputs`, on one column of padding in a `ws4 watch` table; the three gate jobs were green. |
| `39102779086` | `f7cc6d0` | failure | `Notebook outputs` green for the first time; the gate jobs failed with `NoSuchKernel: python3`. |
| `39102026256` | `2026065` | failure | The first run: `000_environment_check` drifted on an environment report, and the check's tests had no kernel. |

The three failures are in section 5 with their causes and remedies. The evidence head is `9bcdcfd`; the
commit that records this report follows it and re-runs the same jobs.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Flow targets in `report_targets.csv` are still mis-reported | `target_status` prices every target as a level target over its period, while the objective prices a `flow` target as a per-period percent series. Measured: an `ndy` target with `minimum: -1` over a series dropping 100 -> 60 is priced at **39.00** by the objective and reported as `met` with **0.00** | reported rather than guessed at, because fixing it means deciding what the report should *show* for a flow target (the period series, or the worst period); recorded in `notes/backlog.md` and in the roadmap's P10 section. Nothing shipped is affected: the sample estate's targets are level targets |
| The Phase 10 launch commit landed with the dashboard red | a roadmap tracker status I wrote said `active (held on the P9.5 export)` where the phase section says `active`, and the command chain ran on past the failing exit status | caught by the workflow validator on the next run and fixed by `0c44c5f`; the tracker row is back to `active`, the holding note is in the phase section, and the lesson (a chain hides an exit status) is in the changelog |
| The pull request is stacked rather than based on `main` | Phase 10 branched from `feature/p9-memory`, which is held open for P9.5 | stated in the roadmap, the changelog, the report and the pull request; one command changes the base |
| The first CI run of this pull request was red, on two jobs | the `Notebook outputs` job found `000_environment_check`'s banner cell differing in CI, because it reports whether `geopandas` is importable — the environment, not the code; and the check's own tests failed in CI because the notebooks they build carried no kernelspec, where the committed notebooks do | the banner cells (the version report and the optional-dependency report) and the rendered `ws4 --help` screen are tagged `no-drift-check` **in the notebook**, so the exclusion is visible in the source; the test fixture sets the same kernelspec the committed notebooks set. Both are recorded here because the job's purpose is to be run where the code is run, and its first real run earned its place by finding exactly the class of thing it was built for |
| The `ws4 watch` progress table drifted in CI by one column of padding | the box a rich table draws is sized to the width of its values, which is a rendering detail, not a claim — masking the values left the padding to differ | the check now flattens layout as well: box-drawing characters and column padding are removed and **counted** (`layout x5706` on a full run), so the content of every cell is still compared and the width it was drawn at is not. A unit test pins two differently-padded renders of the same content as equal |
| The check's tests need a kernel wherever they run | `nbclient` arrives with `nbsphinx`, but `ipykernel` — which ships the `python3` kernel spec a session looks for — did not, so the gate jobs failed with `NoSuchKernel` while the `Notebook outputs` job passed (it installs it explicitly) | `nbclient` and `ipykernel` are now named in `requirements-dev.txt` with the reason, so the suite carries what it needs instead of relying on a transitive dependency |
| The `Notebook outputs` CI job had not run before this pull request | the job was added in this phase | it runs on every pull request now, and this phase's own pull request is its first — **success** on the second run, after the fixes above |

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
