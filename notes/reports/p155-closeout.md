# P155 close-out: 3D fire scene and synthetic tree stands

Date: 2026-11-08
Status: active; PR #919 queued for maintainer approval
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
- run scene discovery, payload/viewer APIs, and a Fire workspace with a shared timeline,
  tree/fragment inspection, and Scene A/B comparison;
- a standalone viewer and a web viewer served with vendored Three.js.

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
- Demo replay: 9 fragments, 22,500 trees, 40 fire events, 61.09 ha burned, 47.46 m/min
  head ROS, 11.32 m flame, 0-120 minute ignition window.
- Standalone viewer: 22,500 trees loaded, play/pause/scrub/reset controls worked,
  `?bloom=0` rendered with no page errors, and 60-minute playback reported 247 burning,
  7,538 burnt, and 209/5,000 particles at about 20 fps under SwiftShader.
- Fire workspace: opens run1 scene, loads the viewer, populates tree inspection, toggles
  Scene A/B comparison, and has no page errors.
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

PR #919 is open and contains P155.2 through P155.5. It is queued for maintainer approval;
no merge, tag, release, or settings change has been performed.
