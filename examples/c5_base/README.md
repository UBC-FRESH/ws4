# c5 20 × 10-year even-flow base scenario

Initial growing stock (`feature.total.Yield` at year 0): **26,556,411.75**.
Final-period floor: **90% = 23,900,770.58** at period 20 (years 190–199).

The scenario has 20 periods of 10 years. It sets a 1,000,000 per-period harvest
floor on `product.total.Yield`, an even-flow band of ±1% against the final-period
reference, and the final growing-stock floor on `feature.total.Yield`.

Run it from the repository root (adjust the data path if needed):

```bash
python -m ws4.cli optimize \
  --dataset c5_compiled \
  --targets scenarios/c5-base/targets.yaml \
  --out c5-base \
  --years 200 --iterations 5000 --seed 1
```

For a higher even-flow ceiling, run the max-flow probe against the same base
targets; it replaces the per-period level targets with a constant floor and
reports the highest verified advisory ceiling (`--flow even` keeps the band):

```bash
python scripts/max_flow.py \
  --dataset c5_compiled \
  --targets scenarios/c5-base/targets.yaml \
  --account product.total.Yield \
  --out c5-base-max-flow \
  --years 200 --period-width 10 --iterations 300 --probes 8 --flow even --flow-tolerance 0
```

For a higher even-flow ceiling, use the max-flow probe with the same targets and
`--flow even`; it replaces the per-period level targets with a constant floor and
reports the highest feasible advisory ceiling. The 1.0M floor is the base case,
not a certified maximum.

The sample runs root contains only `run-base` as a browsing baseline. Old test
runs and scenario fragments are archived under
`/srv/shared-data/gep/ws4/archive/c5-parity2025-scenarios-20261028`.

After editing in the web UI, save through the normal targets path; the service
should be started with:

```bash
--targets scenarios/c5-base/targets.yaml
```
