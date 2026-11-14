# P204 report: aligned LANDIS process transition

Date: 2026-11-14
Phase: P204 (#1199)
Branch: `feature/p204-transition-alignment`
Design note: `notes/design/ws4-transition-alignment.md`

## Result

The aligned WS4 process now matches the P200 Biomass_core reference within **0.169%** at
year 10.

| Point | P202 | P204 | Reference |
| --- | --- | --- | --- |
| year 1 | 2694.6167 | **2694.0** | 2694 |
| year 10 | 8832.0582 | **9444.0** | 9460 |
| year-10 error | -6.64% | **-0.169%** | — |

## What changed

- Age increments before growth.
- Age mortality is computed before competition and ANPP.
- `aNPPAct` and `mBio` receive the published `mAge` adjustments and floors.
- Biomass updates use integer truncation.
- The comparison runs 11 annual updates to cover time 0 plus years 1–10.

## Evidence

- `tests/test_landis_spatial_comparison.py`: **2 passed**.
- `tests/test_ecosystem_landis.py` and `tests/test_ecosystem_ensemble.py`: **16 passed**.
- Full dashboard: **OVERALL: GREEN**.
- P199 kernel parity tests remain unchanged.

## Residual

The remaining 16 g/m² difference is consistent with regeneration and module bookkeeping that
the process does not implement. It is not calibrated away.

## Boundary

One toy landscape, one trait set, one horizon. No observed-data claim. The process remains a
simplified cohort transition, not a full Biomass_core module.

## Next

Add regeneration and cohort-death bookkeeping to the process, or move to a larger reference
landscape. The residual should be explained before claiming full module parity.
