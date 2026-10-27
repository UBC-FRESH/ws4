# DIS-04 TSA 23 deferral scenario

Date: 2026-10-27
Candidate: DIS-04
Scope: compare the existing `ft_warm` schedule with a scenario that defers
treatments on blocks dominated by the NTEMS `not_recovered` class.

## Inputs

- TSA 23 compiled dataset: `runtime/ws4/compiled_ft_econ` (102,128 blocks).
- Existing schedule: `runtime/ws4/ft_warm/schedule.csv` (44,388 blocks, offsets 0-4).
- Recovery status: `examples/recovery_tsa23/regen_status.csv`.
- Source: NTEMS fire recovery, 1986-2012 disturbance, 1985-2017 observation,
  30 m, OGL-C.

## Scenario

Remove all scheduled rows for blocks whose dominant recovery status is
`not_recovered` (411 blocks, 6,048 ha). A second variant also removes `slower`
blocks (433 blocks).

## Result

| Scenario | Harvested volume (m3) | Delta | Treated area | Delta |
| --- | ---: | ---: | ---: | ---: |
| baseline | 138,502,037 | - | 317,710 | - |
| defer not-recovered | 137,123,922 | -1,378,115 (-1.00%) | 314,131 | -3,579 (-1.13%) |
| defer not-recovered + slower | 137,077,876 | -1,424,160 (-1.03%) | 313,920 | -3,790 |

The 411 scheduled blocks cover 6,048 ha, but the treated-area reduction is
3,579 because some treatments are not operable at the current track/age. The
volume impact is about 1%.

## Interpretation

The recovery layer can be used as a **scenario overlay** on the existing
schedule without changing the objective. The next decision is whether a 1%
volume impact justifies a planning constraint, a deferral window, or a
remediation priority rule. That is a management decision, not a data-contract
change.

## Verification

- Baseline and both scenarios run with `ws4 simulate --years 5`.
- Scenario comparison: `examples/recovery_tsa23/recovery_scenario_comparison.csv`.
- No objective or constraint change.
