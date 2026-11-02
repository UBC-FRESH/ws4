# Phase close-out report: P87 Stand density management and AU Explorer

Phase: P87 Stand density management and AU Explorer
Parent issue: #628
Pull request: #658, `feature/p87-sdmd-au-explorer` into `main`
Evidence head: `e2b758c`
Report commit: `f3fb67f` (notes and changelog only; that change does not trigger a code CI run)
Date: 2026-11-02
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #658, and delete the branch `feature/p87-sdmd-au-explorer`.
2. Close parent issue #628 with a closeout comment that cites the merge commit.
3. Launch the next phase: the next free phase number at approval time (P91 today). Create
   its branch, set the phase statuses in `ROADMAP.md`, create its child issues as sub-issues,
   and start its first task.

Settings changes: none. No tag, release, visibility, Pages, branch-protection, or external
account change is requested.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Six table contracts with validators that can fail; two-AU fixture passes | `64fd1ca`, 38 schema tests | met |
| PSP/VRI/LiDAR ingestion labels synthetic rows and refuses canopy-only TPH | `c387d93`, 30 ingest tests | met |
| SDMD stored as vector isopleths, envelope and trajectory assessment, unreviewed diagram refused | `ebb08a4`, `443377b`, `fa371c6`, `13f37af`; 41 diagram tests | met with a stated limit: the committed diagram is a synthetic fixture, not a published digitisation |
| Regimes are ordered state machines; only AU-allowed regimes pass | `0f5c766`, 33 tests; 7→6 regimes and 11→7 entries | met |
| AU Explorer API with a validated constraint write | `4e253f7`, 14 API tests | met |
| AU Explorer tab renders the API contract with provenance and caveats | `e0199f5`, `827a431`; Playwright desktop and iPad landscape | met |
| Solver option space is reduced without losing allowed prescriptions | `cc459d7`, 10 tests; 11 tracks / 13 rows → 7 / 9 | met with a stated limit: trajectory-zone rejection and a cap across blocks in one AU are deferred |
| Gates reject the 863 m3/ha initial volume and flag 1,173 m3/ha | `ws4 sdmd validate --initial-volume 863 --initial-volume-limit 800` exits 1; 1,173 warns above 1,133.8 | met |
| `python scripts/dashboard.py` is green on every commit | dashboard green at `1e1a585` and at each task commit | met |
| Public BC SDMD sources for the species/BEC set | `source_catalog.json`, `bec_variants.csv`, 14 diagrams, 229 variants; 7 source tests | met |

## 2. Workflow compliance

- Parent issue before the branch: **deviation**. The worktree and branch were created before
  parent issue #628. The issue exists before any implementation commit, and it is cited in the
  branch's first commit.
- Branch from `main`: base `213a000` (P86). `origin/main` was merged at `1e1a585` before the
  PR opened.
- Commit messages that start with task IDs: every commit on the branch starts `P87`, except the
  merge commit `1e1a585`.
- Gates for each commit: section 3.
- Roadmap and changelog in step: all task commits update the roadmap and changelog. Two roadmap
  checkbox edits (P87.4 and P87.6) were missed and fixed in `726bca4`; that is recorded as a
  deviation.
- Child issues closed with closeout evidence: #629, #630, #631, #632, #633, #634, #635.
  #636 closes with this report.
- Approval gates: no merge, tag, release, settings, or external action has been taken. The PR is
  queued, not merged.

## 3. Gate evidence

| Commit | Task | Gates |
| --- | --- | --- |
| `64fd1ca` | P87.1 schema, ADR, fixture | dashboard green; 38 schema tests |
| `c387d93` | P87.2 ingestion | dashboard green; 30 ingest tests |
| `ebb08a4` | P87.3 diagram and AU report | dashboard green; 40 diagram tests |
| `443377b` | P87.3 reviewer wording | dashboard green |
| `fa371c6` | P87.3 equation core and page labels | dashboard green; 27 equation tests |
| `0f5c766` | P87.4 regimes and constraints | dashboard green; 33 tests |
| `4e253f7` | P87.5 API | dashboard green; 14 API tests |
| `e0199f5` | P87.6 web tab | dashboard green; Playwright and 3 UI tests |
| `827a431` | P87.6 isopleths and interpretation | dashboard green; browser smoke updated |
| `cc459d7` | P87.7 solver filter | dashboard green; 10 solver tests |
| `13f37af` | P87.3 physical trajectory refusal | dashboard green; 41 diagram tests |
| `726bca4` | P87.8 eight validation gates | dashboard green; 10 validation tests |
| `1e1a585` | merge `origin/main` | dashboard `OVERALL: GREEN` on all seven gates |
| `e2b758c` | P87.8 CI mypy fix | CI run 41402135881: success on every job |

Validation command output at the evidence head:

- `ws4 sdmd validate --sdmd-dir <fixture> --au AU-IDFdk3-FDI`: `warn`; plot support,
  density plausibility, regime completeness, option reduction, and UI payload pass; SDMD fit
  warns because the diagram is provisional; initial volume warns because none was supplied;
  trajectory plausibility warns because the FUEL50 demo path is an extrapolation.
- `--initial-volume 863 --initial-volume-limit 800`: `initial-volume` fails; exit 1.
- `--initial-volume 1173 --initial-volume-limit 2000`: `initial-volume` warns above the
  observed maximum 1,133.8 m3/ha.

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 41402135881 | `e2b758c` | success | Quality gates, clean-checkout contract, notebook outputs, pre-commit parity, and the green dashboard summary all passed. The report commit `f3fb67f` changes only notes and the changelog, so it has no code CI run. |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Branch created before parent issue #628 | The worktree was set up before the issue scaffold | Issue #628 exists before the implementation commits; recorded here |
| Phase started while P86 was `pr-open` | The maintainer requested parallel expansion sessions | Recorded in the roadmap and changelog; branch merged current `main` at `1e1a585` |
| P87.3 "licensed digital copy / forester review" wording implied an unstaffed gate | The plan used that wording; the pilot has no external forester | Named the maintainer as reviewer of record; corrected the docs and ADR at `443377b` |
| The FUEL50 demo trajectory increased both TPH and stem volume | Fabricated demo points used to trigger the extrapolated badge | Replaced with a plausible low-density/larger-tree path; added `validate_trajectory` at `13f37af` |
| P87.4 and P87.6 roadmap checkboxes were left unchecked | Two string replacements did not apply and were not read back | Fixed in `726bca4`; the issue bodies and parent checklist were already correct |
| The initial-volume gate uses the fixture's observed maximum, not the KC dataset | The KC initial volume is not in the repository | The 863/1,173 values are exercised in tests and the CLI; the pilot limitation is stated |
| Trajectory-zone rejection and a cross-block AU cap are not enforced | The compiled matrix has no per-track trajectory table and no AU search state | Deferred in #635 and the roadmap with that reason |
| CI failed on `1e1a585` and `5737e49` at the Types gate | A test called `pd.isna` on a `loc` scalar that CI pandas stubs type more broadly | Fixed in `e2b758c`; CI run 41402135881 is green |

## 6. Next phase

Recommended: **the next free phase at approval time (P91 today), "SDMD pilot digitisation and
trajectory evidence."** The phase should:

1. Digitise the public `fdin`/`fdip` Interior Douglas-fir diagrams into the vector contract and
   have the maintainer review the isopleths; replace the synthetic fixture in the pilot report.
2. Generate FVS-BC and PSP trajectories for the pilot AUs, store them as
   `trajectories/<au_id>/<regime_id>.json`, and run the trajectory gate on real paths.
3. Enforce the SDMD-zone rule and the per-AU entry cap in the solver now that per-track
   trajectories and AU state exist.
4. Close with the pilot AU report, the validation evidence, and a decision on the other BC
   species diagrams.

Open choices and recommended defaults:

- **Pilot AU set:** keep `AU-IDFdk3-FDI` and `AU-IDFdk3-PLI`; reason: they are the fixture and
  the only reviewed AU pair.
- **Digitisation source:** use the public `fdin`/`fdip` PDFs and record URL, version, checksum,
  and reviewer; reason: the source catalog already carries them.
- **Trajectory source:** FVS-BC first, PSP as the observed check; reason: the plan treats FVS
  and PSP as the growth evidence and the diagram as the diagnostic layer.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
