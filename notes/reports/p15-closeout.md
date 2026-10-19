# Phase close-out report: P15 A spread-connectivity account

Phase: P15 A spread-connectivity account
Parent issue: #138
Pull request: #139, `feature/p15-spread-connectivity` into `main`
Evidence head: `6dc2db3`, the head that the gates and the CI runs below cover
Report commit: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-19
Status: approved for merge. The report commit's CI is the last gate.

> **Correction (P16.1, 2026-10-19).** The instance-level acceptance below compared the compartment
> computed on the WS4-treated set with a fire outcome produced by a 3.3× larger treatment. A
> matched-footprint rerun on five seeds withdraws that validation: the fire ranking is not stable and
> the mean order reverses. The account remains a defined fragmentation metric; its fire-response
> validation does not hold. See `p16-bridge-matched.md`.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #139, and delete the branch `feature/p15-spread-connectivity`.
2. Close parent issue #138 with a closeout comment that cites the merge commit.
3. Launch P16: run the spread account against a like-for-like bridge, and settle the account's shape on
   that evidence.

Settings changes, each with its exact command. Each one runs only after its own approval.

- None.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A spatial account that measures the connectivity a fire spreads through | `ws4/spread/accounts.py`; `largest_component` and `percolation_reach` over the fast-edge compartments | met |
| The synthetic oracle shows the patch-size account cannot rank the patterns | `tests/test_spread_accounts.py`: same largest patch for a full-span row and column band; the compartment cuts 490 ha to 210 ha for either full span and leaves 450 ha for a partial band | met |
| The account is usable in a run and by the optimizer | `spread_metrics.csv` and `account_values.csv` per period; whole-schedule pricing; `--spread-accounts` + `--block-coordinates` on `optimize`, `watch` and `calibrate`; `OptimizeConfig.spread_accounts_path` / `block_coordinates_path` | met |
| The TSA23 bridge ranking is reproduced, or the gap is measured | The patch test reproduced exactly (`agree: False`); the compartment reading ranked the three patterns as the fire model does, **82,800 / 104,600 / 187,173 ha** against **19,640 / 19,870 / 20,298 ha** burned, with the area-weighted mean also ordered correctly | met, with the limits recorded in section 5 |
| Documentation and API reference | `docs/reference/spatial.rst` (account, limits, API), `simulator.rst` (`spread_metrics.csv`), `optimizer.rst` (targeting), `notes/design/ws4-spatial-accounts.md` | met |
| Dashboard green | `python scripts/dashboard.py` at `6dc2db3`: **GREEN**, 7 gates, 579 tests | met |

## 2. Workflow compliance

- Parent issue before the branch: #138 was opened before the phase branch; the branch name and the
  parent issue were recorded in `ROADMAP.md`.
- Branch from `main`: `git merge-base --is-ancestor main HEAD` passes; the branch is four commits ahead.
- Commit messages that start with task IDs: 4 of 4 (`P15:`, `P15.1`, `P15.2`, `P15.3`).
- Gates for each commit: section 3.
- Roadmap and changelog in step: `ROADMAP.md` and `CHANGE_LOG.md` were updated in the P15.3 commit. The
  three P15 changelog entries carried unfilled `#NNN` placeholders; they are removed in the report
  commit.
- Child issues closed with closeout evidence: **none were created** (see section 5).
- Approval gates: the phase branch, pushes, the pull request and the issue comment were within the
  phase allowance. The merge was explicitly approved by the maintainer on 2026-10-19, conditional on
  the phase objectives being met and no loose ends remaining. No settings, tags or releases are touched.

## 3. Gate evidence

| Commit | Gates | Result |
| --- | --- | --- |
| `e393b22` P15.1 | local tests, lint, format, types | green at the time |
| `e4bb837` P15.2 | `python scripts/dashboard.py`: lint, format, types, tests, validator, docs, docstrings | **GREEN**, 579 tests |
| `6dc2db3` P15.3 | `python scripts/dashboard.py`: the same seven gates | **GREEN**, 579 tests |

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 39310019242 | `6dc2db3` | success | Quality gates, green dashboard summary, pre-commit parity, notebook outputs — all four jobs passed |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| No child issues for P15.1 to P15.3 | The phase was tracked in #138 and `ROADMAP.md` only | Recorded here; the roadmap and changelog carry the task-level state, and the changelog placeholders are removed |
| P15.1's directed definition was replaced in P15.3 | Running the real bridge instance showed the directed reach read a boundary corridor (3,390.6 ha identical for all three patterns) and reversed the mean | The account was redefined on the compartment evidence; the module, design note and changelog record the failed reading rather than hiding it |
| The bridge is not a like-for-like test | The fire model treats 177,088 ha of whole scheduled blocks; the WS4 FT product reaches about 46,600 ha of managed fragments | Named as the first task of P16; the phase claims a validated ranking, not a validated mechanism |
| The validation is one stochastic seed and a 3% fire spread | The bridge run used the instance's original settings | P16 repeats it across seeds and at a matched footprint |
| The FT product's curve reads 4.0 | A dataset-compile defect, not a WS4 defect | The finding is written up; the guard belongs to P16 and the compile fix to the dataset owner |

## 6. Next phase

**P16: The bridge at the same footprint.** The account is now validated on an arrangement effect whose
size may be partly a footprint artefact. Until both sides treat the same land, and the ranking survives
more than one seed, the paper claim is suggestive rather than established.

- P16.1 Run the fire model on the WS4-treated masks and across five seeds — the three patterns, the
  matched footprint, the mean and p90 burned, and the ranking stability. Delegated to the thesis
  environment, whose fire model owns the pattern generation.
- P16.2 Refuse the 4× area product loudly at load time — when a `products.csv` label names an area or
  treated product and its curve exceeds 1.0 anywhere, report it rather than returning a plausible
  number.
- P16.3 Decide the account's final shape on the matched evidence: keep the compartment as the
  headline, and either retire the orientation claim for good or specify the anisotropic-rate metric
  that would earn it.

Acceptance: the matched-footprint ranking reported across seeds with the treated area matching on both
sides, the load-time check able to fail, and the account's documentation stating the final scope.

## 7. Decision

- [x] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
