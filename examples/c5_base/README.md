# c5 20 × 10-year even-flow base scenario

Initial growing stock (`feature.total.Yield` at year 0): **26,556,411.75**.
Final-period floor: **90% = 23,900,770.58** at period 20 (years 190–199).

The scenario has 20 periods of 10 years. It sets base harvest floors of 700,000 per period on `product.Yield.managed.Conif`
and 50,000 on `product.Yield.managed.Decid`, an even-flow band of ±1% against the
final-period reference for each species, and the final growing-stock floor on
`feature.total.Yield`.

Run it from the repository root (adjust the data path if needed):

```bash
python -m ws4.cli optimize \
  --dataset c5_compiled \
  --targets scenarios/c5-base/targets.yaml \
  --out c5-base \
  --years 200 --iterations 5000 --seed 1
```

For a higher even-flow ceiling, run the max-flow probe against the same base
targets. It replaces the per-period level targets with a constant floor and
reports the highest verified advisory ceiling:

```bash
python scripts/max_flow.py \
  --dataset /srv/shared-data/gep/ws4/ws4/tmp/parity2025/c5_compiled \
  --targets /srv/shared-data/gep/ws4/ws4/tmp/parity2025/scenarios/c5-base/targets.yaml \
  --account product.Yield.managed.Conif \
  --out /srv/shared-data/gep/ws4/archive/c5-base-max-flow-20261028c \
  --years 200 --period-width 10 --iterations 3000 --probes 6 --flow even --flow-tolerance 1
```

The 2026-10-28 run of that command returned an advisory ceiling of **0** and did
not verify a positive floor. The base scenario therefore remains a policy floor,
not a certified maximum. Report:
`/srv/shared-data/gep/ws4/archive/c5-base-max-flow-20261028c/max_flow.md`.

The sample runs root contains only `run-base` as a browsing baseline. Old test
runs and scenario fragments are archived under
`/srv/shared-data/gep/ws4/archive/c5-parity2025-scenarios-20261028`.

After editing in the web UI, save through the normal targets path; the service
should be started with:

```bash
--targets scenarios/c5-base/targets.yaml
```
