# P88 factorized GPU account basis

Parent issue: #637
Branch: `feature/p88-factorized-gpu`
Evidence commit: `28f0c64`
Pull request: #642

## Result

P88 replaces the rejected all-account effects matrix with an account-independent
structural basis plus padded GPU feature and product pricers. A target account is now a
small curve table over the same option structure.

The full TSA24 descriptor archive is
`runtime/factorized/tsa24-factorized.npz`:

- 50,096,749 options;
- 2.94 GB of arrays;
- 1.5 s load in the earlier build check.

## Exactness

| Path | Batch | Exact error | GPU peak |
|---|---:|---:|---:|
| `feature.Volume`, 20 ten-year periods | 64 genomes | **0.0** | **7.1 GB** |
| `product.Yield.managed.Total` | 64 genomes | **8.9e-7** | **4.6 GB** |
| mixed feature/product, 4 target cells | 64 genomes | **3.5e-9** | **9.3 GB** |

The feature result was compared with the flat exact array evaluator over all period cells.
The product result was compared with the flat product evaluator. The mixed result compares
cells `(9, feature.Volume)`, `(9, product.Yield.managed.Total)`,
`(19, feature.Volume)`, and `(19, product.Yield.managed.Total)`.

## Timing and memory

| Measurement | Result |
|---|---:|
| Feature padded build | 146.7 s |
| Feature upload | 1.1 s |
| Feature 64-genome batch | **0.694 s** (92 genomes/s) |
| Product padded build | 83.6 s |
| Product upload | 0.47 s |
| Product 64-genome batch | **0.0255 s** (2,507 genomes/s) |
| Mixed account build | 226.3 s |
| Mixed 64-genome, 4-cell batch | **0.093 s** (686 genomes/s) |

Host peak RSS was 14.6 GB for the segment build and 11.6 GB for the event build. The
build preflight refuses to start when available memory is below 2.5 times the padded
estimate plus 4 GB.

## Commands

```bash
python examples/gpu_effects/benchmark_factorized_feature.py \
  --dataset /srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance/build/compiled \
  --targets /srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance/config/ws4/targets/evenflow_tsa24_ltsy.yaml \
  --artifact /srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance/runtime/factorized/tsa24-factorized.npz \
  --seed-schedule /srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance/runtime/tsa24-ltsy-schedule.csv \
  --account feature.Volume --years 200 --period-width 10 --genomes 64

python examples/gpu_effects/benchmark_factorized_product.py \
  --dataset /srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance/build/compiled \
  --targets /srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance/config/ws4/targets/evenflow_tsa24_ltsy.yaml \
  --artifact /srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance/runtime/factorized/tsa24-factorized.npz \
  --seed-schedule /srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance/runtime/tsa24-ltsy-schedule.csv \
  --account product.Yield.managed.Total --years 200 --period-width 10 --genomes 64

python examples/gpu_effects/benchmark_factorized_switch.py \
  --dataset /srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance/build/compiled \
  --targets /srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance/config/ws4/targets/evenflow_tsa24_ltsy.yaml \
  --artifact /srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance/runtime/factorized/tsa24-factorized.npz \
  --seed-schedule /srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance/runtime/tsa24-ltsy-schedule.csv \
  --feature feature.Volume --product product.Yield.managed.Total \
  --years 200 --genomes 64
```

## Account switching

`GenomePopulation` accepts an optional `FactorizedAccountSet`. When a target reads a cell
absent from the sparse table, the population:

1. leaves `EffectTable.cells` unchanged;
2. stores the missing cells as `_extra_cells`;
3. prices only those cells for the generation;
4. concatenates the values before the existing objective pricer.

Disabling that target removes the extra cells. The synthetic integration test checks that
the table cell count does not change and that every population score matches
`IncrementalObjective`.

## Limits

- The padded maxima are TSA24-specific: two fragments per option, four segments per
  fragment, three product events per option.
- A factorized account is priced for candidate rows, not a seed-only row outside the
  candidate list.
- Watched feature offset `-1` is not a target cell; the factorized target path rejects it.
- A one-time structural build is still required. Account switches only rebuild a
  few-hundred-kilobyte curve table.
- A standalone live growing-stock display path is not included.

## Safety

The rejected all-account matrix is not implemented. The effect-table builder keeps the
post-P85 worker limit and preflight, and the lean path avoids the full 50M-entry row
index dictionary. The OOM cause and controls are recorded in
`docs/gpu_effect_table_postmortem.md`.

## Deferred

- A full watcher run under a mixed target set.
- A live display account path separate from the objective effect table.
- Extension of the structural build to a model whose padded maxima differ from TSA24.

## Verification

```bash
pytest tests/test_factorized_effects.py tests/test_gpu_effects.py tests/test_gpu_ga.py -q
python scripts/check_workflow.py
python scripts/dashboard.py
```
