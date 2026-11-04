# P124.1 3D estate replay

Date: 2026-11-04
Parent: #781
Child: #815
Branch: `feature/p124-3d-replay`

## Goal

Add an experimental coarse 3D view of the current block layer without terrain,
machine, or editing controls. The 2D map remains authoritative.

## Design

- A Map-workspace button opens a full-screen 3D overlay.
- The renderer is an original Canvas 2D orthographic projection; no third-party
  renderer is vendored.
- Block polygons are extruded by a coarse height. Treated blocks are taller;
  `age` is used when the geometry carries it. The existing period slider drives
  the same feature set.
- Drag orbits, wheel zooms, reset restores the view, Escape closes.
- Clicking a block selects it through the same `showDetail` path as the 2D map.
- The view refuses more than 2,000 block features and names the count.
- No edit, run, terrain, or machine capability is added.

## Verification

Pending implementation.
