# Phase close-out report: P14 Optimizer search for aggregate targets

Phase: P14 Optimizer search for aggregate targets
Parent issue: #133
Pull requests: #135 (`P14.1`, merged as `809cc1d`) and #137 (`P14.2`, merged as `cc37fde`)
Evidence head: `a4c8be0`, the head that the gates and the CI runs below cover
Report commit: the commit that adds this report in the maintenance pull request.
Date: 2026-10-19
Status: closing. The phase's code is merged; this report adds the instance-level evidence that was
deferred because the instance was not on this machine.

## Recommendation

1. Close parent issue #133 with a closeout comment that cites the merged commits and this report.
2. Keep the TSA23 result as the instance-level evidence; no code changes are recommended.

Settings changes, each with its exact command. Each one runs only after its own approval.

- None.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| The optimizer reaches the floor without breaching the ceiling, where it previously did not | Synthetic instance: unseeded penalty **34,800** (8,700 against a 30-block floor); seeded penalty **0** (50,750), haul 507,500 exactly on the ceiling. Test: `tests/test_seeding.py` | met |
| The mechanism is general | `ws4/opt/seeding.py` reads the targets only (a `minimum` is a floor, a `maximum` a ceiling); it names no model, account label or treatment | met |
| No regression | Dashboard GREEN at each commit (570 tests at P14.1, 573 at P14.2); parity acceptance unchanged | met |
| The TSA23 instance reaches penalty 0 without breaching the budget | Run on the real instance (below): seeded **penalty 0.0**, treated **9,999.96 ha**, cost **$199,999,193** against a $200,000,000 ceiling; unseeded **15,758.97** | met |

### The instance-level run (deferred at merge, now measured)

Targets v1: a floor of 16,000 on `product.Treated.managed.FT` at year 0 and a $200M ceiling on
`product.FuelTreatmentCost`. Targets v2: both bounds on the cost account over a five-year horizon
(`year: 4`, `period_width: 5`), a floor of $80M (4,000 ha).

| targets | run | value | penalty | status |
| --- | --- | ---: | ---: | --- |
| v1 | unseeded, 500 iterations | 241.03 (60.26 ha) | 15,758.97 | below |
| v1 | `--seed-greedy`, 200,000 iterations | 39,999.84 (9,999.96 ha) | **0.00** | met |
| v2 | unseeded, 500 iterations | $3,550,963 (177.55 ha) | 76,449,037 | below |
| v2 | `--seed-greedy`, 200,000 iterations | $199,999,524 (9,999.98 ha) | **0.00** | met |

Both seeded runs report `time_limit_reached: false`, so the budget did not cut them and the result is
reproducible from the seed. The budget binds in both: the seed fills to the ceiling rather than the
floor, which is what the instance can buy at its cost rate.

**One caveat belongs to the dataset, not to P14.** `product.Treated.managed.FT` reads **4.0000×** the
treated hectares because its curve is 4.0 where an area product needs 1.0. The v1 seeded run meets the
16,000 floor as that account reports it; its real treated area is 9,999.96 ha, confirmed by
`product.FuelTreatmentCost / 20,000` to four decimals. The v2 targets sidestep the defect by using the
cost account. The defect is written up and the guard against it is P16.2.

## 2. Workflow compliance

- Parent issue before the branch: #133.
- Branch from `main`: `feature/p14-optimizer-seeding`; P14.1 and P14.2 merged by pull request.
- Commit messages that start with task IDs: P14.1 and P14.2.
- Gates: section 3.
- Roadmap and changelog in step: the tasks were ticked and the changelog carried both entries; the phase
  status is set in the report commit.
- Child issues closed with closeout evidence: #134 and #136 were closed with their merges.
- Approval gates: both pull requests were approved and merged as phase work. No settings changes.

## 3. Gate evidence

| Commit | Gates | Result |
| --- | --- | --- |
| `809cc1d` P14.1 | `python scripts/dashboard.py` | GREEN, 570 tests |
| `cc37fde` P14.2 | `python scripts/dashboard.py` | GREEN, 573 tests |
| `a4c8be0` (evidence head) | `python scripts/dashboard.py` | GREEN, seven gates, 579 tests |

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 39315534976 | `a4c8be0` | success | CI: quality gates, dashboard summary, pre-commit parity, notebook outputs |
| — | `809cc1d`, `cc37fde` | success | Merged pull requests #135 and #137; their checks were green before merge |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The instance criterion was deferred at merge | The TSA23 instance was not on this machine | Run now: both target versions reach penalty 0 when seeded, with the budget respected |
| The v1 floor was set on a 4×-inflated account | A dataset curve, not a WS4 rule | Recorded here; the v2 targets use the cost account; the load-time guard is P16.2 |

## 6. Next phase

P15 (the spread-connectivity account) is complete; its close-out report is `notes/reports/p15-closeout.md`.
The proposed P16 is the bridge at a matched footprint, the 4× guard, and the account's final scope.

## 7. Decision

- [x] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
