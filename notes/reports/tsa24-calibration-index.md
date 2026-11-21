# TSA24 fire calibration index

This is the entry point for the fire calibration work. It records the experiment sequence, the
reports, the code commits, and the local analysis scripts.

## Current state

- Code baseline: `2b694256` on `main`
- Worktree: `worktrees/ws4-calibration`
- Local analysis scripts: `work/fire_regime/`
- These scripts are currently local analysis code, not part of the package contract.
- Reports are under `notes/reports/`.

## Scripts

| Script | Purpose |
| --- | --- |
| `six_tiles.py` | Six-tile VRI/SRTM fetch and real-versus-homogeneous fire comparison |
| `regime24.py` | 24-tile real-layer fire ensemble and historical comparison |
| `tier24.py` | Three-tier suppression sweep |
| `continuous24.py` | Continuous containment-area sweep |
| `fine50.py` | 50 m fire-grid and active-spread experiments |

The scripts depend on public VRI, SRTM, and BC Wildfire sources. Cache and output locations are
local and are not part of the repository contract.

## Calibration sequence

| Step | Evidence | Commit |
| --- | --- | --- |
| VRI fuel and SRTM six-tile pilot | `notes/reports/tsa24-vri-fuel-growth-pilot.md` | `a2f75d7b` |
| 24-tile real-layer regime calibration | `notes/reports/tsa24-24-tile-regime.md` | `98e96ced` |
| Three-tier suppression sweep | `notes/reports/tsa24-three-tier-calibration.md` | `96003e3c` |
| Continuous containment and resolution limit | `notes/reports/tsa24-continuous-containment-resolution.md` | `9128ec7f` |
| 50 m fire-grid calibration | `notes/reports/tsa24-fine50-fire-grid.md` | `f8900415` |
| 50 m hot-weather diagnostic | `notes/reports/tsa24-fine50-hot-weather.md` | `c615f80e` |
| Weighted-weather containment | `notes/reports/tsa24-weighted-weather-containment.md` | `a7681693` |
| Compressed tile dataset and optimizer | `notes/reports/tsa24-compiled-tile-optimizer.md` | `a65b06d` |
| TSA24 block subset optimizer and risk | `notes/reports/tsa24-compiled-block-subset.md` | `7284e2f1` |
| 50 m block-support policy | `notes/reports/tsa24-block-support-50m.md` | `24f514a9` |
| Full-estate support and fire path | `notes/reports/tsa24-full-estate-support.md` | `12eb4f89` |
| Active-spread closed-line diagnostic | `notes/reports/tsa24-active-spread-contained.md` | `05692c67` |
| Conditional-escape diagnostic | `notes/reports/tsa24-conditional-escape-diagnostic.md` | `28f0f6f8` |
| Relative suppression fit and validation | `notes/reports/tsa24-relative-suppression-fit.md` | `af1be150` |
| 10-hour active-day relative fit | `notes/reports/tsa24-relative-10h.md` | `20d3c320` |
| Region-level suppression fit | `notes/reports/tsa24-region-suppression.md` | `063fda14` |
| Active spread hours | `ws4/ecosystem/growth_fire.py` | `7110541e` |
| Region-level suppression support | `ws4/ecosystem/growth_fire.py` | `1d46d410` |
| Tail-fire audit with antecedent FWI | `notes/reports/tsa24-tail-audit.md` | `2b694256` |

## Key parameters and seeds

The calibration experiments use deterministic seeds recorded in the reports and scripts. The
main recurring parameters are:

- 250 m and 50 m fire grids
- 10 active spread hours per day
- 90-day antecedent FWI spin-up for tail events
- relative contained/escaped fractions
- escape caps up to 30,000 ha in the region-level fit

## Data sources

- BC VRI WFS: forest vegetation polygons and crown/species attributes
- SRTM elevation via public terrain tiles
- BC Wildfire perimeters and historical incident records
- public TSA24 compiled inventory and block geometry

## Boundary

The tail audit found that antecedent FWI spin-up is required. The current calibration is not a
final regime: the central distribution is close, but the extreme tail and independent
validation are still unresolved.
