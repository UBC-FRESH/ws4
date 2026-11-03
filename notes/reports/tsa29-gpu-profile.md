# P112 TSA 29 GPU profile

Date: 2026-11-03
Status: complete; PR #757

## Change

The existing TSA 29 effect table is valid for a table-backed GPU profile. The
public portal now exposes a `base` profile using:

- dataset: `build/compiled`
- effects: `runtime/gpu-effects/effects-lean.pt`
- targets: `config/ws4/targets/evenflow_tsa29.yaml`
- seed: `runtime/seed_oldest_first_tsa29.csv`
- cache: `runtime/gpu-cache`

The profile library is `config/ws4/profiles/gpu.yaml` in the TSA 29 instance.

No factorized archive is required.

## Smoke

Zero-generation run with replay:

- `factorized`: **false**
- incumbent objective: `2007828120.8709574`
- verified objective: `2007828120.8709567`
- exact replay: **true**
- wall: **115.2 s**
- RSS: **7.37 GB**
