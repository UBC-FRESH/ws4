> **HISTORICAL / LEGACY-MAP NOTE (2026-11-26).** This report describes the superseded frozen support map. The canonical map is the positive-overlap, cell-share map documented in `support-map-builder.md`; counts and applied results here are legacy sensitivity only.

# P164.8 regional calibration in the full-estate path

Status: integration evidence

The regional calibration map was wired into `build_relative_fire_source` through its
region-config path and run against the full TSA24 compiled dataset.

## Region map

- TSA24 support grid: 1,957 × 2,237 cells at 250 m
- 24 calibration tiles assigned from the fixed tile manifest
- 349,650 grid cells lie inside the calibrated tile rectangles
- 311,648 support cells are covered (28.0% of 1,111,565)
- 25 region entries: 24 tiles plus a default for cells outside the calibrated tiles

## Dataset run

- full compiled dataset loaded in 141.6 s
- one ignition in region `t13`
- regional suppression config selected from `work/fire_regime/results/region-calibration.json`
- source emitted 3 fire events
- burned area: 22.26 ha
- full-estate evaluation completed

## What this verifies

The region-level calibration is no longer a standalone JSON artifact. It is accepted by
`build_relative_fire_source`, the source accepts the full support map and a region grid, and the
resulting fire events run through the compiled `ProcessDataset`.

## Boundary

This integration run uses homogeneous C2 fuel and flat terrain for the full support grid because
full TSA24 VRI/SRTM layers are not present. The regional parameters control suppression, not
landscape fuel. The calibrated regions cover 28.0% of the support cells (311,648 of 1,111,565); cells outside
the fixed tiles use the default config.

## Next

The calibrated map is ready for a run with full real layers. That is a data-coverage task, not a
new fire-model calibration.
