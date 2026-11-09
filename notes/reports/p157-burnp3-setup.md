# BurnP3 reference setup

Date: 2026-11-09
Parent: #923 P157
Task: #945 P157.10
Status: environment installed; library/scenario setup still required

## Goal

Run a BurnP3-based reference comparison for the Dogrib fire. BurnP3 is the
Canadian Forest Service reference fire-risk framework; BurnP3+ wraps FireSTARR and
Prometheus.

## Installed

- SyncroSim 3.1.32 Linux console (`mono SyncroSim.Console.exe`).
- `burnP3Plus` 2.6.11.
- `burnP3PlusFireSTARR` 1.5.7.
- Bundled FireSTARR `tbd` binary, version 0.9.2.1; marked executable.
- R 4.3.3 with `sf`, `terra`, `tidyverse`, `data.table`, `lubridate`, `rlang`,
  `rsyncrosim`, and `arrow` 26.0.1.
- System GDAL 3.8.4 and Mono 6.8.0.

Package check:

```text
burnP3Plus               2.6.11
burnP3PlusFireSTARR      1.5.7
```

## Remaining blockers

1. **No BurnP3 library** has been created or imported yet. The BurnP3+ Quickstart
   template is distributed through SyncroSim Studio’s “From Online Template”
   flow, not as a standalone file in the package.
2. The Dogrib scenario still needs to be mapped into BurnP3 datasheets: landscape
   rasters, weather, ignition/start perimeter, fuel crosswalk, and Scenario 2b
   weather patches where supported.

## Scenario 2b limitation

The BurnP3+FireSTARR transformer starts from a point ignition
(`burnP3Plus_DeterministicIgnitionLocation`) and does not pass a start perimeter to
FireSTARR. It also builds hourly weather from the daily
`burnP3Plus_DeterministicBurnCondition` table. It therefore cannot reproduce the
Dogrib 13:00 start perimeter/fuel break or the Scenario 2b river-polygon wind patch.

BurnP3+Prometheus is the faithful route for that scenario, but Prometheus currently
fails under Wine. BurnP3+FireSTARR can still be run from the Dogrib ignition point as
a separate reference, but it is not an apples-to-apples Scenario 2b comparison.

## Next

- If a Windows host is available, run BurnP3+Prometheus on Scenario 2b.
- Otherwise run BurnP3+FireSTARR from the Dogrib ignition point and label it as a
  point-ignition reference, not a Scenario 2b reproduction.
- Compare either result with observed, WS4 Scenario 2b, and the direct FireSTARR run.

This is a real setup task, not a failed model run. The direct FireSTARR comparison
is already complete; BurnP3 is the wrapper/reference workflow around it.
