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

## Managed-stock follow-up

Revalidated the harvest-only `base` profile on 2026-11-08: zero-generation objective
`1311809142.7037165`, verified objective `1311809142.7037134`, `exact_match: true`,
48.35 seconds, 7.3 GB RSS.

The portal's generated stock90 target also reads `feature.Yield.managed.Total`. The lean
table is target-coupled and has 42,483,063 rows, so a lazy extension is infeasible
(more than nine minutes and 36 GB RSS before it was stopped). TSA 29 therefore keeps the
state-engine fallback for the stock floor until a prebuilt stock-cell basis or factorized
archive is available. See `p150-gpu-extension-guard.md`.
