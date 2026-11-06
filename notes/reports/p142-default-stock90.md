# P142 default stock-guarded even-flow scenario

Date: 2026-11-06
Status: pr-open
Branch: `feature/p142-default-stock90`
Parent issue: #846
Task issue: #847

## Summary

New instances should open with a scenario worth solving immediately. `ws4.opt.default_scenario`
generates a cached default target file from an instance's own base targets:

- keeps the existing even-flow and period structure;
- adds a final-period `feature.Yield.managed.Total` floor at 90% of initial managed
  growing stock;
- when no stock guard exists, raises managed harvest level aspirations (default 2x) so
  the objective has a useful direction;
- leaves flow terms and existing stock guards alone;
- never writes the instance's source target file.

`find_initial_stock` scans the instance's runs for the newest initial managed growing-stock
value, preferring the aggregate total.

The UI default Solve wall-clock budget is raised from one minute to three minutes.

## Verification

- Unit tests cover initial-stock detection, newest-run selection, volume aspiration,
  stock-floor insertion, and preservation of an existing guard.
- `python scripts/dashboard.py`: `OVERALL: GREEN. Every gate passed.`
- Portal integration and live verification pending the merge.
