# Phase close-out report: P76 C5 base scenario

Phase: P76, C5 base scenario
Parent issue: #543
Pull request: #547, `feature/p76-c5-base-scenario` into `main`
Evidence head: `0678d32`, the head that CI run `40650166791` covers
Report commit: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-28
Status: merged and closed on 2026-10-28 as `9ac4136`.

## Recommendation

1. Squash-merge pull request #547 and delete `feature/p76-c5-base-scenario`.
2. Close tasks #544–#546 and parent #543 with the merge commit.
3. Deploy `v83` and restart c5 with the cleaned sample and the new scenario.

Settings: the live c5 `--targets` path must change to
`/srv/shared-data/gep/ws4/ws4/tmp/parity2025/scenarios/c5-base/targets.yaml`.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| The c5 sample contains one baseline run and one base scenario. | Runs root now lists only `c5_compiled`, `run-base`, and `scenarios`; 112 old run/scenario entries were moved to `archive/c5-parity2025-scenarios-20261028`. | Met |
| The scenario validates through the targets loader. | `load_targets` returns 22 rows; `tests/test_c5_base_scenario.py` passes. | Met |
| The scenario has periods 1–20 with width 10. | Loader reports periods 1–20; every row has `period_width: 10`. | Met |
| The final growing-stock floor is 90% of initial. | `feature.total.Yield` at period 20 has minimum **23,900,770.58**; initial is **26,556,411.75**. | Met |
| The README gives exact run and max-flow commands. | `examples/c5_base/README.md` and the installed sample copy. | Met |
| The c5 service opens cleanly on the new scenario. | Local c5 service lists one baseline run and 22 targets; target charts show **20 periods**. | Met |
| `python scripts/dashboard.py` is green. | All seven gates green at `0678d32`; CI run `40650166791` success. | Met |

The base scenario sets a 1,000,000 per-period `product.total.Yield` floor, a ±1% even-flow band
against the final-period reference, and the final growing-stock floor. The README explains that
1,000,000 is a base floor and that `scripts/max_flow.py --flow even` is the advisory ceiling probe.

## 2. Workflow compliance

- Parent issue before the branch: #543 created before `feature/p76-c5-base-scenario`.
- Branch from `main`: forked from `5bd892d` (P75 status).
- Commit messages: P76 task IDs.
- Child issues: #544–#546 are linked as sub-issues and are closed after merge.
- Approval: the user asked for the cleanup and base scenario and approved P75; merge approval is
  covered by that request.

## 3. Gate evidence

`python scripts/dashboard.py` at `0678d32`: lint 0.07 s, format 0.09 s, types 0.60 s,
tests 140.05 s, validator 1.13 s, docs 4.68 s, docstrings 4.12 s. Overall **GREEN**.

A one-iteration c5 run using the scenario completed, produced 22 target rows, and was archived
with the old test runs after validation.

## 4. CI evidence

| Run ID | Head commit | Conclusion |
| --- | --- | --- |
| 40650166791 | `0678d32` | success |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The archive lives outside the sample. | The user asked to clear the sample, not destroy evidence. | Old runs and fragments are under `archive/c5-parity2025-scenarios-20261028`. |
| The baseline was cropped from years 0–200 to 0–199. | A 20 × 10-year scenario must expose 20 periods, not an extra partial period. | `account_values.csv` and `product_values.csv` in `run-base` now end at 199; the target charts show 20 periods. |
| The 1,000,000 harvest floor is a base policy, not a certified maximum. | The target model prices bound violations; the true maximum needs the max-flow probe. | The README includes the exact `scripts/max_flow.py --flow even` command. |

## 6. Next phase

No P77 is scoped. The next recommended work is to run the max-flow probe on this cleaned scenario
and record the advisory even-flow ceiling as a companion run.

## 7. Decision

- [x] Approve as written.
