# P155 close-out: 3D fire scene and synthetic tree stands

Date: 2026-11-08
Status: complete; PR #919 squash-merged as `a01e847`
Branch: `feature/p155-fire-3d`
Parent issue: #877
Task issue: #882

## Result

P155 is implemented on the branch and ready for maintainer review. The phase is not
merged, tagged, or released without approval.

The vertical slice now includes:

- deterministic synthetic tree inventory and `ws4.fire.scene.v1` package;
- Nemora/VRI tree adapter and P156 growth-field ignition;
- fire, smoke, ember, and heat-haze visual pass;
- a 12-polygon public TSA 24 VRI cluster with 12,588 Nemora-placed synthetic stems;
- run scene discovery, payload/viewer APIs, and a Fire studio with a shared timeline,
  tree/fragment inspection, Scene A/B comparison, fullscreen canvas, collapsible panels,
  and From-ignition/Jump-to-fire controls;
- a standalone viewer and a web viewer served with vendored Three.js.
- Public Pages: https://ubc-fresh.github.io/ws4/fire-demo.html
- Fire studio preview: http://10.232.253.210:8798/?view=fire
- Live portal static viewer: http://10.232.253.210:8790/instance/femic-northisland-instance/static/fire-demo/viewer.html

## Acceptance evidence

| Criterion | Evidence |
|---|---|
| Same polygons, seed, and generator reproduce the scene | `examples/fire_3d_demo.py` ran twice; all output SHA-256 hashes matched. |
| Trees inside fragments; stand area/basal area conserved | `tests/test_scene_trees.py`, `tests/test_scene_nemora.py`, and `tests/test_scene_ignition.py` pass. |
| Every ignition maps to a P144 event; replay digest recorded | `tests/test_scene_package.py` event-mapping test; demo manifest reports `c02e39ac...f93e1d`. |
| Viewer plays the fire with flames, smoke, and burnt states | P155.5 headless Chromium check; screenshot at 60 minutes shows tree canopy, fire front, smoke, and burnt region. |
| Manifest marks synthetic layer and provenance | Scene manifest asserts `synthetic_trees: true`; VRI/Nemora tests check adapter source/seed/version. |
| Dashboard green | `python scripts/dashboard.py`: **OVERALL: GREEN** on all seven gates. |

## Verification matrix

- `tests/test_scene_package.py`, `test_scene_trees.py`, `test_scene_nemora.py`,
  `test_scene_ignition.py`, `test_fire_browser.py`, and the web scene API test:
  **36 passed**.
- VRI demo: 12 fragments, 12,588 trees, 16 fire events, 95.42 ha burned, 27.07 m/min
  head ROS, 8.40 m flame, 0-239.9 minute ignition window.
- Standalone viewer: 12,588 trees loaded; Play/Pause/scrub/reset worked; no page errors.
- Fire studio: scene selector populated, viewer iframe loaded, tree/fragment inspection
  populated, Scene A/B toggle works, Play and From-ignition/Jump-to-fire advance the fire,
  and the desktop layout hides duplicate HUD and header period controls.
- The live 8790 portal has the static viewer; the Fire studio itself is previewed on 8798.
  Promoting it to 8790 requires merging the P155 branch into the portal deployment branch.
- Full dashboard: lint, format, types, tests, validator, docs, and docstrings all green.

## Visual acceptance and limits

The visual acceptance is the P155.3 screenshot plus the P155.5 headless replay. This is a
procedural planner view, not a CFD or photoreal smoke simulation. Hardware GPU performance
was not measured; only SwiftShader was available. Ember visibility was not separately
verified. The synthetic tree layer is not calibrated to a real VRI inventory.

## Documentation

- `docs/reference/fire-scene.rst` covers the package, payload, and web endpoints.
- `docs/reference/web.rst` documents the Fire workspace and `/api/fire` routes.
- `notes/backlog.md` records the remaining visual/hardware limits.
- `notes/reports/p155-visual-checklist.md` carries the final checklist.

## Approval

PR #919 contained P155.1 through P155.5 and was squash-merged as `a01e847`. The phase
branch was deleted. The Fire studio is still previewed on 8798; the live 8790 portal has the
static viewer until the portal deployment branch is updated.
