# Acceptance checks (P3.1)

The P2 build is checked against its acceptance criteria. The checks are repeatable with
`scripts/acceptance.py`. The reference compiled matrices and the full sample dataset are external
inputs (not committed), so the builder check takes them as `--case RECIPE FRAGMENTS REFERENCE`
arguments and the sample is run separately.

## 1. Matrix builder against reference compiled matrices

Each case compiles a recipe and a fragment inventory and compares the compiled matrix to a reference
matrix directory, using the established table names (`tracknames.csv`, `strata.csv`, `treatments.csv`,
`blocks.csv`, `features.csv`, `products.csv`, `protoaccounts.csv`). Row counts and feature, product,
and account label sets are compared.

Result: **9 of 9 core variants match** exactly.

| Variant | tracks | strata | treatments | blocks | features | products |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| pct_light | 351 | 351 | 263 | 399 | 11063 | 26905 |
| pct_heavy | 351 | 351 | 263 | 399 | 11009 | 26824 |
| pct_moderate | 351 | 351 | 263 | 399 | 11063 | 26905 |
| intensive_light | 732 | 732 | 963 | 427 | 20485 | 82216 |
| intensive_moderate | 732 | 732 | 963 | 427 | 20485 | 82216 |
| intensive_heavy | 732 | 732 | 963 | 427 | 20005 | 81352 |
| intensive_light_standstructure | 732 | 732 | 963 | 427 | 20485 | 82216 |
| ctfert_l15h5 | 553 | 553 | 605 | 427 | 17094 | 59024 |
| ctfert_l20h0 | 532 | 532 | 563 | 427 | 16548 | 56546 |

`protoaccounts` matches exactly (attributes and groups) on all nine.

## 2. Simulation

- Synthetic prototype: compiles, validates, and returns account values. **pass**.
- C5 end-to-end: ingest produces `tracks 1558`, `strata 3551`, `treatments 1398`, `blocks 16174`,
  `features 20151`, `products 4940`, `accounts 52`, `groups 12567`, `fragments 16174`, `curves 130423`;
  validation reports **0 problems**; a 30-year run over 16174 fragments returns **1020 values across 34
  accounts in 15.5 s**.

## 3. Optimizer

- Synthetic: a maximum target on `feature.Volume` at year 0 is **met** (the run writes `schedule.csv`,
  `account_values.csv`, `report_accounts.csv`, `report_targets.csv`, and `summary.json`).
- C5: the run completes and writes its outputs; the target report says **met**.

## 4. Spatial and road

- Synthetic: block 1 routes to destination 3 at 3000 m and cost 3.0. **pass**.
- C5: `vertices 27231`, `segments 36721`, `destinations 3`, `linkages 12567`; block 1's nearest
  destination is about 66.4 km away.

## 5. Programmatic model API

A model loaded from a compiled dataset and written back produces the same `fragments`, `blocks`,
`features`, `products`, and `accounts` tables. **pass**.

## 6. Gates

- `python -m pytest`: **218 passed**; branch coverage **94.78 percent** (the gate is 90).
- `python scripts/dashboard.py`: **OVERALL: GREEN**.
- `python scripts/acceptance.py --case ...`: **OVERALL: PASS** (builder, prototype, optimizer, roads,
  and api).

## Open items

The P2 deferred items remain open and are tracked in `notes/backlog.md`. No acceptance check failed.
