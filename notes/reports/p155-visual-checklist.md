# P155.3 visual checklist: fire and smoke

Phase: P155
Branch: `feature/p155-fire-3d`
Scene: 12 VRI polygons, 12,588 synthetic trees, 5,000-particle budget
Capture: `notes/reports/p155-visual-check.png`

## What was verified

- The generated viewer parses as an ES module (`node --check` on the module body).
- Headless Chromium/SwiftShader loaded the viewer with no page errors.
- Playback at 60 minutes showed 138–152 burning trees, 4,574–4,601 burnt trees, and
  622–1,198 active particles against a 5,000 budget.
- The software-rasterizer frame rate was about 20 fps at 1280×800. This is a floor, not a
  hardware measurement.
- The viewer exposes `window.__ws4FireStats` with fps, particle count, budget, burning and
  burnt counts, scene time, and time unit.
- The screenshot shows the VRI polygon layout, tree canopy, smoke, and the fire front at the
  downwind edge.

## Visual features in this slice

- Flame particles use a procedural noise and temperature ramp shader with additive blending
  and a soft camera-depth fade.
- Smoke particles use curl-like wander, buoyancy, and a soft billow shader.
- Embers are short-lived ballistic particles with a warm glow.
- A screen-space heat-haze pass distorts the scene above the fire.
- Bloom is enabled by default; `?bloom=0` is the low-cost fallback.
- Burnt crowns shrink and darken; trunks darken; stand polygons develop a gradual burnt
  fraction instead of a binary square flash.
- The HUD reports frames per second and active particles against the budget.

## Manual browser checklist

- [ ] Play, pause, reset, and scrub the timeline.
- [ ] Confirm flames are animated and attached to burning trees.
- [ ] Confirm smoke rises and drifts, and embers are visible near the front.
- [ ] Toggle `?bloom=0` and confirm the viewer still renders.
- [ ] Confirm burnt crowns shrink and the stand tint follows the burnt fraction.
- [ ] Confirm the Focus fire button frames the active front.
- [ ] Confirm the HUD particle count stays at or below the manifest budget.
- [ ] Check a lower-end GPU and record the observed frame rate.

## Limits

- This is a procedural real-time visual, not a CFD smoke solver or a photoreal VFX shot.
- The heat haze is a screen-space distortion, not a temperature field.
- No offline high-fidelity smoke tier is implemented in this slice.
- LOD is the existing instanced tree mesh; there is no distance-based tree LOD yet.
- Three.js still loads from a CDN. Vendoring is part of the web workspace.
- The headless frame rate uses SwiftShader, so it does not predict hardware performance.
