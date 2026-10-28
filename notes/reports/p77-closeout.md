# Phase close-out report: P77 C5 even-flow ceiling

Phase: P77, C5 even-flow ceiling
Parent issue: #550
Pull request: #552, `feature/p77-c5-max-flow` into `main`
Evidence head: `f447d42`, the head that CI run `40656171477` covers
Date: 2026-10-28
Status: ready for approval. Not merged.

## Recommendation

1. Merge the scenario correction and probe record.
2. Keep the base scenario floors as a policy baseline, not a certified maximum.
3. Run a longer/warm-started max-flow probe before claiming a positive ceiling.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Probe completes and writes its report. | Two probes completed under `/srv/shared-data/gep/ws4/archive/c5-base-max-flow-20261028b` and `...c`; both wrote `max_flow.md`, probe logs, and a best schedule. | Met |
| Stock floor remains in every probe. | The base targets were passed unchanged; only harvest-level targets were replaced by the constant floor. | Met |
| README records the ceiling and reproduction command. | `examples/c5_base/README.md` records the 0 advisory ceiling and the exact command. | Met |
| Dashboard green. | All seven gates green at the working head; see section 3. | Met |

The probe at 3,000 iterations, six probes, `--flow even`, and 1% flow tolerance returned:

```json
{"ceiling": 0.0, "feasible": false}
```

This is a **negative result**: no positive even-flow floor was verified. It is not a
certified maximum, and it does not prove the base floors are infeasible; the probe is a
finite search without a warm/primed schedule.

## 2. Scenario correction

The initial P76 base used `product.total.Yield`, but the optimizer prices the species
accounts (`product.Yield.managed.Conif` and `.Decid`) rather than the total row; a
2,000-iteration probe priced the total row at zero. The corrected base scenario uses:

- 20 × 10-year periods;
- conifer floor **700,000** and deciduous floor **50,000** per period;
- ±1% even-flow bands on each species;
- final `feature.total.Yield` floor **23,900,770.58** (90% of initial **26,556,411.75**).

The corrected file is checked in at `examples/c5_base/targets.yaml` and installed in
`scenarios/c5-base/targets.yaml`.

## 3. Gate evidence

`python scripts/dashboard.py`: lint 0.12 s, format 0.11 s, types 27.28 s, tests 136.51 s,
validator 0.88 s, docs 15.49 s, docstrings 2.56 s. Overall **GREEN**.

## 4. CI evidence

| Run ID | Head commit | Conclusion |
| --- | --- | --- |
| 40656171477 | `f447d42` | success |

## 5. Limits

- A zero ceiling is not evidence that no positive floor exists.
- The probe has no warm/primed schedule; the optimizer’s flow target can be infinite while
  the reference period is zero.
- The base scenario is a policy floor plus an even-flow band. It is runnable and
  documented, but it is not a certified maximum-harvest result.

## 6. Next step

Run a warm-started or much longer probe and record whether any positive floor is feasible
before changing the scenario floors.
