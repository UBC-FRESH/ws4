# TSA24 LTSY scenario profile library

Date: 2026-11-02
Status: active profile library

The TSA24 LTSY variants now have a small named profile library instead of ad hoc target
paths.

## Profiles

```text
config/ws4/profiles/ltsy.yaml
```

| Name | Formulation |
|---|---|
| **base** | all-period ±5% even flow with the 90% managed-stock guard |
| baseline | late-period flow, periods 11–20 ±1%, no stock guard |
| nostock | all-period ±5% control without the stock guard |

`base` is the default.

## Watcher

```bash
./run_ltsy_watch.sh 5000              # base
PROFILE=baseline ./run_ltsy_watch.sh 5000
PROFILE=nostock ./run_ltsy_watch.sh 5000
```

Each profile defaults to its own schedule output:

```text
runtime/tsa24-ltsy-base-schedule.csv
runtime/tsa24-ltsy-baseline-schedule.csv
runtime/tsa24-ltsy-nostock-schedule.csv
```

Explicit `TARGETS`, `ACCOUNTS`, or `SCHEDULE_OUT` still override the selected profile.

## CLI/UI surface

```bash
ws4 scenario-profiles --profiles config/ws4/profiles/ltsy.yaml
ws4 scenario-profiles --profiles config/ws4/profiles/ltsy.yaml --name base --json
```

`--json` is the machine-readable surface for a future UI. `--shell` emits the resolved
target, account, and schedule variables for shell integration.

## Validation

- profile-library unit tests cover resolution, duplicate names, missing targets, CLI JSON,
  and shell output.
- `PROFILE=baseline` hot-cache smoke: 20.8 s, wrote the baseline schedule.
- default `base` hot-cache smoke: 20.9 s.
- `base` remains the frozen default profile.

These profile smoke runs are interface checks, not policy results.

## Archive

```text
/srv/shared-data/gep/ws4/archive/tsa24-ltsy-profiles-20261102/
```

Contains the profile library, target files, runner, smoke schedules, README, and checksums.
