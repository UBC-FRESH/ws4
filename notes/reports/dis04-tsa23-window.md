# DIS-04 TSA 23 deferral-window scenario

Date: 2026-10-27
Candidate: DIS-04
Scope: compare a 20-year TSA 23 schedule with 5- and 10-year deferral of
treatments on blocks dominated by NTEMS `not_recovered`.

## Inputs

- TSA 23 compiled dataset: `runtime/ws4/compiled_sf_risk` (102,128 blocks).
- Existing 20-year schedule: `runtime/ws4/abatement_bc/sim_6400000000/schedule.csv`
  (52,901 blocks, offsets 0-19).
- Recovery status: `examples/recovery_tsa23/regen_status.csv`.
- Source: NTEMS fire recovery, 1986-2012 disturbance, 1985-2017 observation,
  30 m, OGL-C.

## Scenario

The 491 scheduled not-recovered blocks (7,502 ha) have their treatment offset
increased by 5 or 10 years. A shifted offset beyond 19 is not executed within the
20-year horizon.

- 5-year deferral: 42 blocks (1,032 ha) fall beyond the horizon.
- 10-year deferral: 61 blocks (1,558 ha) fall beyond the horizon.

## Result

| Scenario | Harvested volume (m3) | Delta | Treated amount | Delta |
| --- | ---: | ---: | ---: | ---: |
| baseline | 164,420,200 | - | 402,851 | - |
| defer 5 years | 164,307,385 | -112,815 (-0.069%) | 402,108 | -742 |
| defer 10 years | 164,266,776 | -153,424 (-0.093%) | 401,663 | -1,187 |

The 20-year schedule is much larger than the 5-year `ft_warm` smoke schedule, so
the same 491 blocks produce a sub-0.1% volume effect rather than the earlier
~1%.

## Interpretation

The deferral window is technically feasible but has a small aggregate volume
effect on this schedule. A hard constraint is not justified by this result
alone. Keep recovery as an informational overlay unless a planner values the
specific not-recovered blocks or a longer horizon changes the impact.

## Verification

- Baseline, defer-5, and defer-10 runs use `ws4 simulate --years 20`.
- Comparison: `examples/recovery_tsa23/recovery_window_comparison.csv`.
- No objective or constraint change.
