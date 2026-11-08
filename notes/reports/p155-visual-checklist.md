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

- [x] Play, pause, reset, and scrub the timeline. Verified in P155.5: clock advanced to
  60.0 minutes on scrub, reset returned to 0.0, and play/pause ran without errors.
- [ ] Confirm flames are animated and attached to burning trees.
- [ ] Confirm smoke rises and drifts, and embers are visible near the front.
- [x] Toggle `?bloom=0` and confirm the viewer still renders. P155.5 loaded the fallback
  with no page errors.
- [x] Confirm burnt crowns shrink and the stand tint follows the burnt fraction. The
  P155.5 screenshot shows the burnt region and dark crowns.
- [x] Confirm the Focus fire button frames the active front. P155.5 clicked it at 60
  minutes with no page error; camera framing was not independently measured.
- [x] Confirm the HUD particle count stays at or below the manifest budget. The P155.5
  screenshot showed 209 / 5000 particles.
- [ ] Check a lower-end GPU and record the observed frame rate.

## Limits

- This is a procedural real-time visual, not a CFD smoke solver or a photoreal VFX shot.
- The heat haze is a screen-space distortion, not a temperature field.
- No offline high-fidelity smoke tier is implemented in this slice.
- LOD is the existing instanced tree mesh; there is no distance-based tree LOD yet.
- Three.js still loads from a CDN. Vendoring is part of the web workspace.
- The headless frame rate uses SwiftShader, so it does not predict hardware performance.

## P155.5 final limits

- Smoke was visible in the screenshot; ember visibility was not separately verified.
- Only SwiftShader was available; no hardware GPU frame rate was measured.
- The viewer is a procedural planner view, not a CFD or photoreal smoke simulation.
- The synthetic tree layer is not calibrated to a real VRI inventory.
- The standalone viewer still uses a CDN Three.js import; the WS4 web viewer uses the
  vendored module.
