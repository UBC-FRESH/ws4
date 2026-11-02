# P89 mixed-target factorized search and live switching

Parent issue: #643
Branch: `feature/p89-mixed-target-search`
Evidence commit: `293df43`
Pull request: #648

## Result

P89 runs the P88 factorized account set end to end on the full TSA24 model. The sparse
effect table keeps its original 200 `product.HarvestedVolume.managed.Total.CC` cells; the
feature stock and second product account are priced as factorized target cells.

The account correction is material: TSA24 exposes `feature.Yield.managed.Total`, not
`feature.Volume`. The P89 reruns use the real stock series and replace the earlier
zero-vs-zero feature evidence.

## Full TSA24 mixed population

Command:

```bash
python examples/gpu_effects/run_factorized_mixed_population.py \
  --dataset /srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance/build/compiled \
  --targets /srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance/config/ws4/targets/evenflow_tsa24_ltsy.yaml \
  --artifact /srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance/runtime/factorized/tsa24-factorized.npz \
  --table /srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance/runtime/gpu-effects/effects-lean.pt \
  --seed-schedule /srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance/runtime/tsa24-ltsy-schedule.csv \
  --feature feature.Yield.managed.Total \
  --product product.Yield.managed.Total \
  --years 200 --period-width 10 --population 64 --generations 2 --check 0
```

Result:

| Measurement | Result |
|---|---:|
| Sparse table cells, before and after switch | **200 -> 200** |
| Factorized target cells | 11 |
| Factorized build | 229.6 s |
| Population construction | 38.2 s |
| Target switch | 4.53 s |
| Two-generation run | 14.87 s |
| Evaluations | 192 |
| Throughput | **12.9 genomes/s** |
| Best objective | 474.3942462931474 |
| Exact replay objective | 474.3942462931473 |
| Objective error | **5.7e-14** |
| GPU peak | **9.27 GB** |
| Host peak RSS | **15.98 GB** |

The target switch leaves `EffectTable.cells` unchanged. The factorized cells are the
feature stock at offset 199 and the second product account at offsets 190-199.

## Corrected P88 pricer evidence

| Path | Exact error | 64-genome batch | GPU peak |
|---|---:|---:|---:|
| `feature.Yield.managed.Total`, 20 periods | **2.2e-5** | **0.706 s** (90.7/s) | **7.2 GB** |
| `product.Yield.managed.Total` | **8.9e-7** | **0.0255 s** (2,507/s) | **4.6 GB** |
| mixed feature/product, 4 cells | **1.1e-5** | **0.093 s** (685/s) | **9.3 GB** |

The errors are absolute and small relative to the stock and harvest totals. The corrected
feature benchmark is no longer a zero-vs-zero comparison.

## Watcher display path

`run_gpu_watch` no longer calls `ensure_cells` for display accounts when a factorized
account set is available. `_incumbent_values` combines:

- table cells and objective factorized cells already in `GenomePopulation.totals`;
- requested display cells priced once per incumbent from `FactorizedAccountSet`.

A synthetic test watches `feature.Volume`, confirms the effect-table cell count is
unchanged, and confirms the display frame is produced.

## Watcher CLI smoke

The existing TSA24 LTSY watcher entrypoint was run in plain mode with the factorized
archive and both accounts:

```bash
cd /srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance
PLAIN=1 SCHEDULE_OUT=runtime/tsa24-ltsy-factorized-smoke.csv ./run_ltsy_watch.sh 2
```

The frame showed both `product.HarvestedVolume.managed.Total.CC` and
`feature.Yield.managed.Total`. The feature windows ran from 165M to 782M over the 20
periods, and the objective frame reported 40.4M with 192 evaluations across 208,255
blocks. The watcher loop elapsed 1.2 s after the one-time factorized build. The output
schedule was written to `runtime/tsa24-ltsy-factorized-smoke.csv` (2.9 MB).

This is a two-generation smoke run, not a production search result. The harvest level
remained below the 100M period aspiration in periods 11-20.

## Padded cache startup

The structural cache is now separate from the 2.9 GB flat artifact:

- cache: `runtime/factorized/tsa24-factorized.padded.pt`
- size: **6.0 GB**
- cold start with rebuild and cache write: **252.0 s**
- hot start with cache load: **19.44 s**
- hot watcher loop: **1.64 s**

The hot start is a **13x** improvement. The feature/product curve tables are still built
in memory per account because they are only a few hundred kilobytes; the cache stores the
large padded structural tensors and lookup metadata.

CLI:

```bash
python -m ws4.cli gpu-watch \
  --factorized runtime/factorized/tsa24-factorized.npz \
  --factorized-cache runtime/factorized/tsa24-factorized.padded.pt \
  ...
```

The TSA24 wrapper passes `FACTORIZED_CACHE` through. The hot run reproduced the same
objective and 128 evaluations as the cold run.

## Final growing-stock floor

Initial managed growing stock (`feature.Yield.managed.Total` at offset 0):
**411,559,095.33 m3**. The 90% floor is **370,403,185.80 m3** at period 20
(offset 199).

Target file:

```text
config/ws4/targets/evenflow_tsa24_ltsy_stock90.yaml
```

It keeps the LTSY flow and level targets and adds:

```yaml
- account: feature.Yield.managed.Total
  period: 20
  year: 200
  period_width: 10
  minimum: 370403185.80
  min_weight: 10.0
  normalization: auto
  shape: linear
  priority: 1
```

Smoke run:

```bash
PLAIN=1 \
  TARGETS=config/ws4/targets/evenflow_tsa24_ltsy_stock90.yaml \
  SCHEDULE_OUT=runtime/tsa24-ltsy-stock90-smoke.csv \
  ./run_ltsy_watch.sh 2
```

The target window showed period 20 with minimum **370M** and realized **782M**
(`ok`). The run used the hot padded cache: wall **19.31 s**, 192 evaluations, objective
**39,063,621.8857**, 208,255 blocks. The output schedule is
`runtime/tsa24-ltsy-stock90-smoke.csv`.

This is a soft goal-programming aspiration, not a hard feasibility floor, and the smoke
run only demonstrates the target plumbing and display; it is not a production search.

## All-period ±5% even-flow experiment

Target file:

```text
config/ws4/targets/evenflow_tsa24_allperiods5_stock90.yaml
```

It changes the flow target to periods 1-20, reference period 1, ±5%, and keeps the
period-20 managed-stock floor at **370,403,185.80**. The level aspirations remain in
place.

Run:

```bash
PLAIN=1 \
  TARGETS=config/ws4/targets/evenflow_tsa24_allperiods5_stock90.yaml \
  SCHEDULE_OUT=runtime/tsa24-allperiods5-stock90-5000.csv \
  ./run_ltsy_watch.sh 5000
```

Result after 5,000 generations:

| Measurement | Result |
|---|---:|
| Evaluations | 320,064 |
| Search loop | 216.0 s |
| Wall including hot-cache start | 234.17 s |
| Objective frame | 2,751.96 |
| Penalty frame | 459,472,816.01 |
| Final managed stock | **477M** |
| Stock floor | **370M** |
| Harvest periods 2-8 | 48.7-49.6M |
| Harvest periods 9-20 | 53.8-54.2M |

The reference period 1 is 51.5M, so the ±5% band is roughly 48.9-54.1M. The flow is
nearly flat, with periods 3 and 16 just outside that band. The stock floor is comfortably
met. The level aspirations in periods 11-20 remain below their 100M pull; this run is an
even-flow/stock experiment, not a level-target success.

## Scenario archive

The all-period ±5% scenario and its 5,000-generation output are archived under:

```text
/srv/shared-data/gep/ws4/archive/tsa24-ltsy-allperiods5-20261102/
```

see `notes/reports/tsa24-ltsy-allperiods5.md`.

## Limits

- The structural build is still one-time and model-specific.
- Factorized target cells assume candidate rows; seed-only rows outside the candidate
  list are not supported on this path.
- The display path is bounded to the watched account set and the incumbent row.
- A two-generation plain watcher smoke was run; no long production watcher was launched.
  The synthetic test still covers the no-table-extension contract.
- The 12.9 genomes/s mixed search rate includes the existing sparse-table gather and the
  factorized cells; it is not the isolated pricer rate.

## Verification

```bash
pytest tests/test_factorized_effects.py tests/test_gpu_effects.py tests/test_gpu_ga.py -q
python scripts/check_workflow.py
python scripts/dashboard.py
```
