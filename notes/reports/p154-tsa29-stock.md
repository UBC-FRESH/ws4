# P154 TSA 29 GPU managed-stock pricing

Date: 2026-11-08
Status: complete
Branch: `feature/p154-tsa29-stock`
Parent issue: #912
Task issue: #913
Merge commit: `8f5aae0`

## Summary

TSA 29's sparse effect table is target-coupled: 42,483,063 rows over 200 harvest cells.
The default stock90 target also reads `feature.Yield.managed.Total` at offset 199, so the
portal correctly fell back to the state engine instead of attempting a 42.5-million-row
lazy extension.

The reusable fix is a factorized structural archive plus a padded feature cache. The
sparse harvest table stays unchanged; the GPU population prices the missing stock cell
through `FactorizedAccountSet`. The TSA 29 `base` profile now declares:

- `feature.Yield.managed.Total` in its accounts;
- `runtime/factorized/tsa29-factorized.npz`;
- `runtime/factorized/tsa29-factorized.padded.pt`.

The reproducible builder is `examples/gpu_effects/build_factorized.py`.

## Build

Command used:

```bash
python examples/gpu_effects/build_factorized.py \
  --dataset /srv/shared-data/gep/ws4/femic/external/femic-tsa29-instance/build/compiled \
  --targets /srv/shared-data/gep/ws4/femic/external/femic-tsa29-instance/config/ws4/targets/evenflow_tsa29.yaml \
  --cache-dir /srv/shared-data/gep/ws4/femic/external/femic-tsa29-instance/runtime/gpu-cache \
  --out /srv/shared-data/gep/ws4/femic/external/femic-tsa29-instance/runtime/factorized/tsa29-factorized.npz \
  --padded /srv/shared-data/gep/ws4/femic/external/femic-tsa29-instance/runtime/factorized/tsa29-factorized.padded.pt \
  --workers 8
```

Measured on the host:

- structural build: 79.3 s; 42,483,062 options; 2.9 GB archive;
- padded cache: 361.1 s from process start; 6.8 GB;
- `supports('feature.Yield.managed.Total')`: true.

## GPU validation

| Run | Generations | Factorized | Objective | Verified | Exact | Wall |
|---|---:|---|---:|---:|---|---:|
| `web-gpu-20261108-034202-7` | 0 | true | 1911809145.4211097 | 1911809145.4030812 | true | 50.7 s |
| `web-gpu-20261108-034416-7` | 1 | true | 1911809145.4211135 | 1911809145.4030812 | true | 47.7 s |

Both runs report `factorized_cells: [[199, 'feature.Yield.managed.Total']]`. The portal
response has `fallback_reason: null`; the default stock90 target now launches the `base`
GPU profile instead of the state engine.

## Remaining limits

The archive and padded cache are instance-specific and must be rebuilt after a material
change to the compiled model or candidate map. The factorized feature path remains an
approximation for scoring (the exact replay is authoritative); both validation runs
reported a matching exact replay.

Dashboard: `OVERALL: GREEN`.
