# Fire regime calibration work

This directory contains the local calibration scripts and their cache. It is outside the
package contract.

- `data/` holds fetched VRI/SRTM layers, tile caches, potential samples, and generated grids.
- `logs/` holds run logs.
- `results/` holds tracked calibration/risk/optimizer result summaries and the local optimizer trace.
- `*.py` are local analysis scripts driven by public BC VRI, SRTM, and wildfire sources.

Scripts resolve paths relative to this directory. No large inputs or outputs are written under
`/tmp`.

The experiment sequence, evidence map, current commit, and handoff state are in
`notes/reports/tsa24-calibration-index.md`. The estate API handoff is
`notes/reports/p164-8-estate-handoff.md`.

## Local scripts

| Script | Purpose |
| --- | --- |
| `six_tiles.py` | Six-tile VRI/SRTM fetch and real-versus-homogeneous fire comparison |
| `regime24.py` | 24-tile real-layer fire ensemble and historical comparison |
| `tier24.py` | Three-tier suppression sweep |
| `continuous24.py` | Continuous containment-area sweep |
| `fine50.py` | 50 m fire-grid and active-spread experiments |
| `build_full_layers.py` | 133-tile full-TSA24 layer cache with a resumable manifest |
| `risk_ensemble.py` | Five-seed calibrated risk ensemble |
| `optimizer_regional.py` | Bounded region optimizer |
| `full_estate_optimizer.py` | Sharded full-estate optimizer and aggregate evaluation |

The full layer cache is `data/tsa24-full-layers/`; the manifest records the tile bounds.
