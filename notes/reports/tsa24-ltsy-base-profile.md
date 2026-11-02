# TSA24 base LTSY watcher profile

Date: 2026-11-02
Status: base profile active; PR #689

The default TSA24 LTSY watcher now runs the accepted all-period ±5% formulation with the
managed-stock guard.

## Target

`config/ws4/targets/evenflow_tsa24_allperiods5_stock90.yaml`

- all-period even flow, periods 1–20;
- reference period 1;
- ±5%;
- periods 11–20 level aspiration of 100M m³;
- period-20 managed-stock floor of **370,403,185.80 m³**.

The stock floor is a soft guard, not a hard feasibility constraint.

## Evidence base

- P94 comparison: all-period stock and no-stock schedules identical.
- P95 vector cache: the stock-guard search fell from **218.9 s to 44.0 s**.
- Accepted 5,000-generation schedule:
  `44bdba7a6cf95a056410ccda4ab86ed74d144fd5c72e63e9430323060440eb1b`

## Default runner

```bash
cd /srv/shared-data/gep/ws4/femic/external/femic-tsa24-instance
./run_ltsy_watch.sh 5000
```

Default output:

```text
runtime/tsa24-ltsy-base-schedule.csv
```

A hot-cache one-generation smoke run completed in **20.89 s** after loading the padded
cache. The smoke output is not a policy result.

## Archive

```text
/srv/shared-data/gep/ws4/archive/tsa24-ltsy-base-profile-20261102/
```

Contains the target, runner scripts, accepted 5,000-generation schedule, smoke schedule,
README, and checksums.

## Caveats

This is a base LTSY formulation, not a definitive sustainable scenario. Managed
old-seral area is very low, and the unmanaged estate reaches 100% ≥200 years over the
200-year horizon. A 20,000-generation confirmation is intentionally not planned.

## Pull request

PR #689 contains the profile note and planning updates. The watcher and archive live outside this git branch.
