# WS4 UI port plan

Date: 2026-11-03
Status: P122 implemented; P123/P124 planned; PR #783

Sources reviewed:

- FHOPS web UI: `/srv/shared-data/gep/ws4/fhops/src/fhops/web`
- FHOPS Scenario Studio 3D: `/srv/shared-data/gep/ws4/carbon-worktrees/fhops-p43/sandbox/studio`
- FRESH Urban Forest Lab: `/srv/shared-data/gep/ws4/fresh-urban-forest-lab/src/fresh_urban_forest/web`
- HectaresBC catalog: `/srv/shared-data/gep/ws4/fresh-hectaresbc/web`

All are FastAPI plus vanilla JavaScript; no frontend build step is required.
WS4 already has the core shell, MapLibre/SVG map, target editor, reports,
comparison, skins, URL state, and assistant overlay. The plan below adds only
missing interaction value.

## Phase P122: Run timeline and interaction uplift

Branch: `feature/p122-ui-timeline`

### P122.1 Run snapshot cards

Add a compact snapshot above the Reports content using the existing run
`summary.json`: status, objective, exact replay, generations/evaluations,
wall time, blocks scheduled, seed/profile, and ending inventory where present.
Use the same `summary` endpoint; no new backend contract.

### P122.2 Period playback

Add a Play/Pause period control beside the existing period slider. It advances
`setPeriod()` at a fixed cadence, skips while the map is loading, stops at the
last period, and stops when the user scrubs manually.

### P122.3 Schedule timeline

Add a Results → Timeline subview. Read the existing `schedule.csv` through the
reports endpoint, aggregate blocks by treatment and displayed period, and render
a pure-CSS Gantt-like timeline. Clicking a segment sets the active period so the
map and target views follow it. No chart library.

### P122.4 Feedback and shortcuts

Add a small toast surface for save/apply/run/export feedback, a native help
dialog with keyboard shortcuts, `/` to focus search, `m` for Map, `?` for help,
and `Esc` to close overlays. Add actionable empty states for snapshot and
timeline data.

## Phase P123: Assistant context and action chips

Extend the existing Ask overlay with a context packet containing run,
workspace, period, selected block, profile, target filter, and visible account.
Render server-returned action chips such as “Explain penalty” or “Open reports”.

## Phase P124: 3D estate replay (experimental)

Port the useful half of FHOPS Studio/Urban: no terrain or machine editing.
Extrude a coarse block layer by age/treatment, add period playback, selection
sync, and a Three.js orbit view. Keep the 2D map authoritative and gate the
experimental view on a coarse geometry budget.
