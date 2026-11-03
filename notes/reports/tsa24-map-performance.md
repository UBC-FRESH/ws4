# P116 TSA 24 map performance

Date: 2026-11-03
Status: complete; PR #774

## Change

- `/api/geometry/bounds` reads an optional `<geometry>.bounds.json` sidecar
  before parsing the full layer.
- TSA 24 gets a 100 m overview layer for low-zoom vector tiles.
- The geometry build script now writes the bounds sidecar automatically.

## Artifacts

- detail: `runtime/geometry/tsa24-blocks.geojson` (~1.1 GB, 5 m)
- overview: `runtime/geometry/tsa24-blocks-overview.geojson` (~221 MB, 100 m)
- bounds: `runtime/geometry/tsa24-blocks.geojson.bounds.json`

## Verification

- Sidecar returns the projected and WGS84 extents without parsing the detail
  layer.
- Low-zoom tile request returns a valid MVT from the overview.
- Focused web tests cover sidecar hit and malformed-sidecar fallback.
