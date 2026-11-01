# TSA24 GPU acceleration: locked benchmark

Date: 2026-11-01
Status: benchmarked; cloud-portable

## Run configuration

- Dataset: `/srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance/build/compiled`
- Targets: `config/ws4/targets/evenflow_tsa24.yaml`
  - SHA-256: `e4f4f67b4c0bdffbe56ed5dc6fe0912eccbe5f589f0ce51e6a4b5a5f532d7762`
- Seed schedule: `runtime/seed_oldest_first_tsa24.csv`
  - SHA-256: `dbcf53707bc111fa224b2a8d698390115053064d0bf636da82b1bf09ae7a3823`
- GPU: NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition
- Population: 64
- Seed: 7
- Years: 200; period width: 10
- Accounts shown: `product.HarvestedVolume.managed.Total.CC`

Current target policy:

- even flow: priority 1, weight 10,000, ±1% around period 1
- harvest level aspirations: priority 1, weight 100, normalization auto, 70,000,000 per period

## Launch

Hot launch, after compact candidate and base/schedule sidecars were present:

- wall: **11.9 s**
- first population evaluation: **0.31 s**
- before-optimization writer: 92.8 s

Dominant remaining launch costs in the hot path:

- seed index lookup: ~5.7 s
- option-map fill: ~2.5 s
- compact candidate load: ~1.8 s
- effect-table load: ~1.3 s

## Sustained search

| Mode | Generations | Evaluations | Search time | Eval/s |
|---|---:|---:|---:|---:|
| PLAIN | 2,000 | 128,064 | 17.16 s | **7,463** |
| Live, throttled renderer | 2,000 | 128,064 | 20.50 s | **6,247** |
| PLAIN | 20,000 | 1,280,064 | 152.60 s | **8,388** |

20k wall time: **164.9 s**.

The old live renderer path measured ~755 eval/s at 8,678 generations because it
repainted every generation. Throttling live paints to the configured refresh interval
removed the regression. Live mode retains about 84% of plain throughput on a short run;
the 20k sustained run is the throughput reference.

## 20k result

- objective: 4,887.04
- profile: 51.2M–52.6M m³ per 10-year period
- candidate level: about **52M m³/period = 5.2M m³/year**
- still slightly outside the ±1% band around period 1 (51.8M)

This is a near-even-flow compromise, not a certified ±1% solution and not yet a
maximum-sustainable-flow result.

## Artifacts

```text
runtime/gpu-cache/candidates.pkl               597 MB
runtime/gpu-cache/candidates-compact.npz       1.44 GB
runtime/gpu-cache/simulator.pkl                 35 MB
runtime/gpu-effects/effects-lean.pt            1.44 GB
runtime/gpu-effects/effects-lean.pt.base.pt     3.2 KB
runtime/seed_oldest_first_tsa24.csv.pkl        parsed schedule cache
```

The compact candidate cache and base-total sidecar are part of the fast launch. They are
currently local workspace artifacts and must be included in a cloud bundle.

## Code changes

- Compact candidate cache and lazy accessor.
- Vectorized GPU option map; removed the 50M-chain Python copy.
- Persisted base totals and parsed seed schedule.
- Batched GPU pricer now supports priority tiers.
- Target-independent cell basis (`cells=`), `watchable_cells`, persisted
  `basis_accounts`, explicit missing-cell errors.
- Lazy `EffectTable.extend_cells`.
- Target hot reload in the GPU watcher, throttled to once per second.
- Live rendering throttled to the configured refresh interval.
- Tests: GPU population, effect-table, and search suites pass; ruff and strict mypy clean.

## Cloud bundle

Minimum run set:

```text
ws4 source checkout (this branch)
TSA24 build/compiled/
runtime/gpu-cache/candidates-compact.npz
runtime/gpu-cache/simulator.pkl
runtime/gpu-effects/effects-lean.pt
runtime/gpu-effects/effects-lean.pt.base.pt
runtime/seed_oldest_first_tsa24.csv
runtime/seed_oldest_first_tsa24.csv.pkl
config/ws4/targets/evenflow_tsa24.yaml
```

A cheap 16 GB GPU should fit the working set; benchmark the 2k PLAIN case first to choose
the instance class. The effect-table build is a one-time cost and should ship with the
bundle, not be rebuilt per cloud run.

## Known limitations

- The existing TSA24 effect table is still target-cell coupled. The new basis path exists,
  but this table predates it. A table built with `--cell-accounts` is required for fully
  target-independent membership.
- `EffectTable.extend_cells` is in-memory. An interactive extension is not yet persisted.
- The target hot reload path applies cells in the basis and adds new cells lazily; an
  extension can still be expensive for a new account.
- This is a frozen-scenario speed benchmark, not a claim that every landscape benchmark
  will show the same speedup.
