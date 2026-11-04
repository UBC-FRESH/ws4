# P124.1 3D estate replay

Date: 2026-11-04
Parent: #781
Child: #815
Branch: `feature/p124-3d-replay`

## What changed

- Added a Map-workspace **3D** toggle and a full-screen experimental overlay.
- The renderer is original Canvas 2D orthographic code. No third-party 3D library is
  vendored.
- Block polygons extrude by treatment, current treatment, and an optional `age`
  property. The existing period slider and playback drive the replay.
- Drag orbits, wheel zooms, reset restores the camera, Escape closes.
- Clicking a 3D block calls the same `showDetail` path as the 2D map; the selected
  block is highlighted in both views.
- The view refuses more than 2,000 block polygons and names the count.
- The 2D map remains authoritative. No terrain, machine, edit, run, or permission
  controls were added.

## Evidence

- `ws4/web/static/index.html`: 3D toggle, overlay, canvas, controls.
- `ws4/web/static/app.js`: `estate3dHeight`, `estate3dProject`, `estate3dPick`,
  `renderEstate3d`, `openEstate3d`, `closeEstate3d`, and selection/period hooks.
- `ws4/web/static/style.css`: `.estate-3d` overlay and `.map-3d-toggle`.
- `tests/test_web.py`: shell wiring and budget constant.
- `tests/test_web_3d_js.py`: Node projection/height behavior.
- `docs/reference/web.rst`: user-facing limits.

## Verification

```bash
python -m pytest tests/test_web.py tests/test_web_3d_js.py -q
python scripts/dashboard.py
```

Focused web tests: 90 passed. Dashboard: `OVERALL: GREEN`.

## Limits

- The view uses the `age` property only when the configured geometry carries it;
  the normal map payload does not include age.
- It is a coarse orthographic view, not a terrain or machine simulation.
- The 2,000-block gate is a client-side budget, not a server-side geometry contract.
- The Node test covers projection and height helpers, not a real browser frame.
- The 2D map remains the source of truth for selection and URL state.
