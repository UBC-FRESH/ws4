# Fire regime calibration work

This directory contains the local calibration scripts and their cache. It is outside the
package contract.

- `data/` holds fetched VRI/SRTM layers, tile caches, potential samples, and generated grids.
- `logs/` holds run logs.
- `*.py` are local analysis scripts driven by public BC VRI, SRTM, and wildfire sources.

Scripts resolve paths relative to this directory. No large inputs or outputs are written under
`/tmp`.

The experiment sequence and evidence map are in
`notes/reports/tsa24-calibration-index.md`.
