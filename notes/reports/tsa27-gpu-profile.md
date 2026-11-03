# P109 TSA 27 GPU profile

Date: 2026-11-03
Status: complete; PR #747

## Change

GPU profile runs no longer require a factorized archive. A profile needs an
effect table, a candidate/simulator cache directory, and a seed schedule; the
factorized display data remains optional.

The public portal now exposes a TSA 27 `s8` profile using the existing artifacts:

- dataset: `build/compiled`
- effects: `runtime/gpu-effects/effects-s8.pt`
- targets: `config/ws4/targets/evenflow_no_caribou.yaml`
- seed: `runtime/seed_oldest_first_s8.csv`
- cache: `runtime/gpu-cache/s8`

The profile library is `config/ws4/profiles/gpu.yaml` in the TSA 27 instance.

## Compatibility fix

TSA 27 stores candidates as a plain mapping rather than a compact candidate
store. The profile seed helper now supports both forms, so existing TSA 27
caches do not need to be rebuilt.

## Smoke

Zero-generation s8 run with replay:

- `factorized`: **false**
- incumbent objective: `253742197.81549`
- verified objective: `253742197.81548998`
- exact replay: **true**
- wall: **11.5 s**
- reports written: `report_accounts.csv`, `report_targets.csv`

## Pull request

PR #747 contains the optional-factorized worker path, mapping-candidate support, tests, and this evidence.
