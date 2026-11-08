# P155.4 WS4 web Fire workspace

Date: 2026-11-08
Status: complete on the P155 branch; phase awaiting approval
Branch: `feature/p155-fire-3d`
Parent issue: #877
Task issue: #881

## Summary

Fire scenes are now discoverable from the WS4 web service and playable in a Fire
workspace.

- A run exposes a scene when it contains `fire_scene/manifest.json` (or `fire-scene`,
  `fire`, or `scene`) with schema `ws4.fire.scene.v1`.
- `GET /api/fire/scenes` lists scene manifests and summaries.
- `GET /api/fire/runs/{run}` returns one manifest and summary.
- `GET /api/fire/runs/{run}/payload` returns the compact payload from `payload.json`.
- `GET /api/fire/runs/{run}/viewer` serves the viewer with the vendored Three.js module.
- The Fire workspace opens the scene over the main canvas, drives a shared timeline and
  speed, inspects trees and fragments, and compares Scene A with Scene B.
- The scene package now writes `payload.json`; the viewer supports `?embedded=1` and a
  small `postMessage` protocol for timeline and tree focus commands.
- `run-health` exposes **Open fire scene** when the selected run has a scene.

## Verification

- `tests/test_web.py`: scene discovery, payload, manifest, and vendored viewer contract.
- `tests/test_scene_package.py`: `payload.json` is written with the other scene artifacts.
- `tests/test_fire_browser.py`: Fire workspace opens a scene, loads the viewer, populates
  tree inspection, and toggles Scene A/B comparison in headless Chromium.
- Manual smoke: the frame loads 800 trees for a 2x2 fixture; the shared clock advances;
  no page errors.
- Dashboard: `OVERALL: GREEN`.

## Not in this task

The visual quality pass (flames, smoke, embers, burnt-scar shader polish) remains P155.3.
P155.5 still owns the full verification sweep and close-out report. The phase PR stays open
for maintainer approval.
