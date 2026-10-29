# c5 20 × 10-year even-flow base scenario

Initial growing stock (`feature.total.Yield` at year 0): **26,556,411.75**.
Final-period target: **90% = 23,900,770.58** at period 20 (years 190–199). This is a
weighted goal-programming target, not a hard constraint.

The scenario has 20 periods of 10 years. It sets harvest targets on the priced species
accounts (`product.Yield.managed.Conif` and `.Decid`), an even-flow band, and the final
growing-stock target:

- conifer level target: **700,000 per period**
- deciduous level target: **50,000 per period**
- even-flow: **±5%**, referenced to period 1
- final stock target: **23,900,770.58**

## Seed and rotation age

The mean yield curve is built by area-weighting the `product.Yield.managed.Conif` and
`.Decid` curves over the managed THLB. The maximum mean annual increment for this c5
curve is at **rotation age 112 years** (MAI ≈ 1.447 m³/ha/year for conifer). The managed
THLB in the compiled blocks is **71,138 ha**, which implies roughly **635 ha/year**, or
about **6,352 ha per 10-year period**, harvested oldest-first.

The companion seed is `seed_200y.csv` in this directory: a real 200-year schedule with
7,253 scheduled blocks. It primes every period so the even-flow reference is meaningful.

## Run

```bash
python -m ws4.cli optimize \
  --dataset /srv/shared-data/gep/ws4/ws4/tmp/parity2025/c5_compiled \
  --targets /srv/shared-data/gep/ws4/ws4/tmp/parity2025/scenarios/c5-base/targets.yaml \
  --out /srv/shared-data/gep/ws4/ws4/tmp/parity2025/c5-base \
  --years 200 --iterations 100 --seed 1 \
  --initial-schedule /srv/shared-data/gep/ws4/ws4/tmp/parity2025/scenarios/c5-base/seed_200y.csv
```

A 100-iteration seeded run is recorded under
`/srv/shared-data/gep/ws4/archive/c5-base-seeded-20261029`. It meets most harvest
targets; the final stock target remains short. That is a target tension, not a solver
crash. The max-flow probe is still an advisory tool and has not verified a positive
even-flow ceiling.

The sample runs root contains only `run-base`. Old test runs and scenario fragments are
archived under `/srv/shared-data/gep/ws4/archive/c5-parity2025-scenarios-20261028`.
