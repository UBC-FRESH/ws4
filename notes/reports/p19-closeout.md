# Phase close-out report: P19 model-derived spatial layers and map scale

Phase: P19 Model-derived spatial layers and map scale
Parent issue: #161
Pull requests: #162 (spread compartments), #163 (used roads), #164 (stability stop), #166 (period
map control), #167 (resizable assistant) and #170 (MapLibre and basemap)
Evidence head: the P19.4 merge plus the documentation in this report
Date: 2026-10-21
Status: closing.

## Recommendation

1. Close parent issue #161 with a close-out comment citing the pull requests above and this report.
2. Keep MapLibre as the default renderer and the SVG shell as the explicit fallback. A basemap
   needs WebGL and network tiles, so the fallback is part of the contract rather than a legacy path.
3. No settings changes, tags or releases. The embedded assistant remains behind `--allow-agent`.
4. Leave the P19 follow-ups that are genuinely new — MapLibre hatching parity, the external OSM
   dependency and any vector-tile work — in `notes/backlog.md` rather than pretending they shipped.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A run with topology, block coordinates and spread accounts writes the membership map layer | `spread_membership.csv`; service `layer=compartments`; browser class/account controls | met |
| A route run writes segment geometry/use and a distinct overlay | `used_roads.csv`; `/used-roads`; browser **Used roads (run)** | met |
| A stability stop is configurable and recorded | `patience` in solver, CLI, summary and player; solver/helper tests | met |
| The map can use a basemap and scale beyond the SVG shell | MapLibre GL JS + OSM raster basemap, vendored; SVG fallback | met |
| The layer tree and period contracts are unchanged | same modes, filters and period control in both renderers | met |
| The dashboard is green at the phase head | `python scripts/dashboard.py`: GREEN on all gates | met |

## 2. What shipped

- **P19.1 Spread compartments (#162).** `spread_membership.csv` from the spread account, largest
  component first, with area classes; `layer=compartments` and the class/account layer tree.
- **P19.2 Used roads (#163).** Route runs write `used_roads.csv` from the vertices geometry;
  `/used-roads?year=` serves the run's used segments; the map overlay is distinct from the source
  access network.
- **P19.3 Stability stop (#164).** `patience` ends a start after N iterations without an incumbent
  improvement; the summary records it and the player exposes it.
- **P19.4 MapLibre (#170).** Vendored MapLibre GL JS 5.6.1 with an OpenStreetMap raster basemap;
  `--crs` and `format=wgs84` transform geometry and roads with pyproj; SVG remains switchable.
- **P19.5 Period map control (#166).** The map steps by accounting periods from the targets'
  `period_width`, labels the year range, sends `period_start`, and pages with left/right arrows.
- **P19.6 Resizable assistant (#167).** A persisted horizontal drag bar sizes the assistant; a
  double-click resets it.

## 3. Verification

- P19.1/P19.2: model, service and API tests; browser checks against a synthetic membership fixture
  and a real 22,661-row used-road run.
- P19.3: the solver loop was exercised with `patience=5` and a 100-iteration budget; it stops at
  iterations 0–4, not only the helper boundary.
- P19.4: browser at v41 with 12,567 polygons; MapLibre canvas, OSM basemap, current/cumulative/base/
  patch/comparison modes, click detail, source roads, period control and SVG fallback. The CRS test
  maps EPSG:26911 `(662656.9, 5558125.9)` to `(-114.723, 50.153)`.
- P19.5: a 50-year run with 10-year targets shows five periods; Right arrow moves to period 2 and the
  current period's 27 treatments, not only year 19.
- P19.6: 240 px → 380 px, reload restored 380 px, double-click reset 240 px.
- The dashboard is green on the phase head; no settings, tags or releases changed.

## 4. Known boundaries

- The MapLibre basemap is OpenStreetMap raster tiles over the network. Without network the blocks and
  overlays still draw on a blank background; the SVG fallback does not need a basemap at all.
- MapLibre paints the cumulative earlier-period fill as flat tan, not the SVG diagonal hatch.
- The source geometry and roads need the correct `--crs`; the default is WGS84. A wrong CRS is a
  user input error, not silently repaired.
- MapLibre is a WebGL dependency (vendored, BSD); the first-cut dependency-free SVG path remains in
  the shell and in the tests.
