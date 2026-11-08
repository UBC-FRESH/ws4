# 3D fire propagation over synthetic individual-tree stands

Status: idea / queued design
Date: 2026-11-07
Issue: #868
Related: `notes/design/ws4-stochastic-landscape.md`,
`docs/reference/ecosystem-fire.rst`, `docs/reference/ecosystem-package.rst`,
Nemora `src/nemora/synthesis/` and `examples/ws4_synthetic/`,
FHOPS `src/fhops/tree_scene.py` and `src/fhops/tree_replay.py`,
FHOPS Scenario Studio `sandbox/studio/`, WS4 `ws4/web/`

## 1. The idea

Take real WS4 VRI polygon stand maps, populate each stand with a plausible synthetic
individual-tree population, and run the P144 fire process through that population as a
real-time 3D vector animation with flames, smoke, embers, and post-fire tree states.

The two existing pieces already fit:

- **Nemora** generates synthetic stands and stems. `nemora.synthesis.stands` samples stand
  attributes and bootstrap rules; `nemora.synthesis.stems` places trees with Poisson,
  stratified, or clustered point processes and attaches DBH, height, and species;
  `nemora.synthesis.tessellation` builds the landscape mosaic; `nemora.synthesis.ws4_fixture`
  writes a deterministic WS4 fixture. The current `examples/ws4_synthetic` is a 12-polygon
  placeholder, not a real VRI stand map.
- **FHOPS** already exports deterministic tree-scale scenes. `fhops.tree_scene` writes glTF,
  GLB, a camera path, and a standalone HTML viewer; `fhops.tree_replay` replays a tree-scale
  schedule; the Scenario Studio has 2D and 3D editing, terrain alignment, retention overlays,
  and replay. That is the pattern to reuse for the fire scene and the viewer.

The new work is the seam: a synthetic tree inventory contract, a fire-to-scene compiler, and
a real-time fire renderer. The fire physics stays in WS4; the trees are visual and fuel
structure; the viewer is a deterministic playback of the event log, not a baked video.

## 2. Why it is worth doing

The P144 fire process produces an event log and fragment-level accounts. That is the right
audit trail, but it is hard to see. A 3D scene makes the spatial process legible:

- a fire front moves through a real polygon map;
- crown consumption and surface fuel explain why the front stops or runs;
- salvage and post-fire structure are visible, not just tabulated;
- a planner can compare two schedules or two scenarios by watching the same landscape burn
  differently.

It also creates a strong visual test for the data contract: if the trees do not sit in their
polygons, if the fuel is missing, or if the event log and the animation disagree, the scene
shows it immediately.

## 3. Data contract

### 3.1 Synthetic tree inventory

A new table, `ws4.tree.inventory.v1`:

| Column | Type | Meaning |
| --- | --- | --- |
| `tree_id` | string | Stable id within the scene. |
| `fragment_id` | int | The WS4 fragment or VRI polygon. |
| `x`, `y`, `z` | float | Local scene coordinates in metres. |
| `species` | string | Species code. |
| `dbh_cm` | float | Diameter at breast height. |
| `height_m` | float | Total tree height. |
| `crown_ratio` | float | Live crown length / height. |
| `crown_radius_m` | float | Crown radius. |
| `live` | bool | Live or dead at scene start. |
| `decay_class` | int | Dead-wood decay class, 0 for live. |
| `crown_fuel_t_ha` | float | Crown fuel available to the fire. |
| `surface_fuel_t_ha` | float | Local surface fuel. |
| `snag_t_ha` | float | Local snag load. |
| `source` | string | `synthetic` plus the generator and seed. |

The tree table is synthetic. The polygons and their VRI attributes are real; the trees are a
plausible realization, not an inventory measurement. Every scene manifest must say so.

### 3.2 Scene package

A new directory, `ws4.fire.scene.v1`:

```text
fire_scene/
  manifest.json          # schema, provenance, seed, CRS, units, synthetic flag
  trees.parquet          # the tree inventory
  stands.geojson         # VRI polygons and stand attributes
  terrain.json           # optional DEM or a flat ground plane
  fuels.parquet          # per-tree and per-cell fuel loads
  events.json            # the WS4 fire event log
  animation.json         # per-tree ignition, burn duration, consumption
  camera.json            # camera path and keyframes
  scene.glb              # optional portable geometry
  viewer.html            # standalone viewer
```

The scene package is a run artefact. It does not modify the compiled dataset, the ecosystem
package, or the event log.

### 3.3 Animation contract

`animation.json` is derived from the event log, not authored independently:

- per-tree `ignition_time_s` from the fragment fire event and a local sub-fragment spread;
- per-tree `burn_duration_s`, `flame_intensity`, `smoke_source_strength`;
- per-tree `post_fire_state` (consumed crown, blackened stem, snag, fallen);
- per-fragment `front` keyframes for the visual fire edge.

The viewer must be able to replay the same animation from the same scene package and seed.

## 4. Pipeline

1. **Load the VRI polygons.** Use the compiled dataset's fragments and their geometry, or a
   VRI source layer. Keep the polygon attributes that drive the stand synthesis: species mix,
   age, site index, basal area, stems per hectare, and any fuel model.
2. **Sample the stand.** Nemora's stand and stem generators produce a species mix, a DBH
   distribution, a height distribution, and a spatial pattern (Poisson, stratified, or
   clustered). The generator is seeded per fragment, so the same polygon and seed reproduce
   the same trees.
3. **Attach allometry and fuel.** DBH and height come from Nemora's stem attributes; crown
   ratio and radius from species allometry; crown, surface, and snag fuel from the fuel model.
   The result is the `ws4.tree.inventory.v1` table.
4. **Run the fire.** The fragment-level `FireRun` produces the event log. The scene compiler
   maps each fire event to its fragment and builds a local burn schedule. For a more detailed
   front, run a sub-fragment cellular or per-tree spread inside the fragment, constrained by
   the fragment ignition time and the local fuel. The event log remains the authority for the
   fragment-level outcome.
5. **Compile the scene.** Export trees, stands, terrain, fuels, events, animation, camera, and
   the viewer. Use instancing and LOD; a large estate may have millions of trees.
6. **Play it.** The viewer loads the package, draws the terrain and trees, and runs the fire
   animation on a timeline. The same package can be opened from the WS4 web UI.

## 5. Rendering

### 5.1 Geometry

- **Trees**: instanced meshes or billboards, with species-specific crown shapes and colours.
  Reuse the FHOPS tree-scene approach for deterministic geometry, LOD, and camera paths.
- **Terrain**: a DEM mesh or a flat ground plane with a fuel texture. The FHOPS Studio's
  terrain-alignment work is the precedent for keeping trees, ground, and overlays on one
  elevation basis.
- **Ground fuel**: a surface layer of litter, grass, and downed wood, rendered as a textured
  mesh or instanced clumps.

### 5.2 Flames

Use a GPU particle or billboard system with a procedural shader:

- temperature-driven colour ramp (white-yellow-orange-red-dark);
- noise-driven alpha erosion so the flame edge is not a hard card;
- additive blending and soft depth fade;
- per-tree crown ignition volume, so a crown burns from the inside out;
- flame height and intensity from crown fuel and fire intensity;
- embers as small ballistic particles with a short glow.

No external texture or model assets are required; the shaders are procedural.

### 5.3 Smoke

Two quality tiers:

- **Real-time tier**: GPU billboard particles with curl noise, buoyancy, wind, and a soft
  depth-aware fade; a screen-space blur and a light scattering approximation. Cap the particle
  count and spawn only near the active front.
- **High-fidelity tier**: an offline or reduced-rate volumetric pass (raymarched density) for
  a hero shot. This is not the default, because it is expensive and not needed for a planner's
  timeline.

Smoke colour is driven by fuel moisture and combustion completeness: white-grey for a hot
crown fire, darker for smouldering surface fuel.

### 5.4 Light and atmosphere

- time-of-day lighting, with the fire as a moving light source;
- bloom and tone mapping;
- heat haze as a screen-space distortion near the front (optional);
- depth fog and aerial perspective so the landscape reads at scale;
- a burnt-scar overlay after the front passes.

### 5.5 Interaction

- play, pause, scrub, and speed control;
- camera path or free orbit;
- click a tree or fragment for species, DBH, fuel, ignition time, and fire intensity;
- toggle trees, fuels, smoke, flames, and burnt scar;
- compare two scenes side by side, or two scenarios over the same landscape.

## 6. WS4 integration

The scene is a run artefact, like the existing map layers and reports:

- `ws4 fire-scene --run RUN --out SCENE` compiles a scene package from a completed fire run;
- `ws4 fire-scene --dataset DATASET --ecosystem PACKAGE --schedule ...` runs the fire and
  compiles in one step;
- `ws4 web` serves the scene at `/api/runs/{run}/fire-scene` and a `Fire` workspace loads it;
- the viewer is a standalone HTML page first, then a WS4 web workspace.

The P144 `FireResult.write` already writes `events.json`, `disturbances.json`,
`cohorts.csv`, and `summary.json`. The scene compiler adds the tree, fuel, and animation
tables and the glTF/viewer.

## 7. Reuse from Nemora and FHOPS

- **Nemora `synthesis.stems`**: `place_trees_with_dbh`, `attach_tree_attributes`, point-process
  placement. Extend with species-specific allometry and fuel attributes.
- **Nemora `synthesis.stands`**: stand attribute templates, bootstrap plans, and the
  per-fragment assignment logic. Use it to make the synthetic trees follow VRI attributes.
- **Nemora `synthesis.tessellation`**: the landscape mosaic and Voronoi polygons for a
  synthetic test landscape; real VRI polygons replace the Voronoi geometry in production.
- **Nemora `synthesis.exporters`**: GeoJSON and tree-table export patterns.
- **FHOPS `tree_scene`**: deterministic glTF/GLB, camera path, standalone HTML viewer, LOD,
  species colours, and the ground mesh.
- **FHOPS `tree_replay`**: the replay timeline and per-tree state pattern.
- **FHOPS Scenario Studio**: 2D/3D editing, terrain alignment, retention overlays, run history,
  and the "edit then replay" interaction model.
- **WS4 web**: run discovery, JSON endpoints, live SSE snapshots, and the map/plan workspaces.

## 8. Validation

The scene must be a faithful view of a run, not a separate animation:

- **Tree placement**: every tree lies inside its fragment polygon; no tree is outside the
  stand; the spatial pattern is the one the generator declares.
- **Stand totals**: basal area, stems per hectare, and volume are within the configured
  tolerance of the stand target. The synthetic tree list is not claimed to be a measured
  inventory.
- **Fuel conservation**: the crown, surface, and snag fuel totals match the fire event's
  consumed fuel within tolerance.
- **Event consistency**: every animated ignition maps to a fire event; the front order is
  consistent with the event log; the replay digest matches the run.
- **Determinism**: the same polygons, seed, and generator produce the same tree and scene
  package.
- **Performance**: a target tree count and particle budget hold a target frame rate; the
  viewer degrades LOD rather than freezing.
- **Provenance**: the scene manifest marks the trees as synthetic and records the polygon
  source, generator version, seed, and fire run digest.

## 9. Phases

- **F0 — Contract and tree synthesis.** Define `ws4.tree.inventory.v1`; extend Nemora's stem
  and stand synthesis to a real VRI polygon layer; validate placement, allometry, and stand
  totals.
- **F1 — Static 3D scene.** Compile trees, stands, terrain, and fuels; export glTF/GLB and a
  standalone viewer; reuse FHOPS `tree_scene`.
- **F2 — Fragment-level fire animation.** Drive flames, smoke, and burnt scar from the P144
  event log; timeline, camera, and tree state.
- **F3 — Sub-fragment refinement.** Add a local spread model inside a fragment and a per-tree
  ignition schedule; keep the fragment event as the constraint and the audit record.
- **F4 — WS4 web integration.** A Fire workspace, scene endpoint, run discovery, and side-by-side
  scenario comparison.
- **F5 — Quality and scale.** GPU particle budgets, LOD, instancing, large-estate streaming,
  and the optional high-fidelity smoke tier.

## 10. Risks and open questions

- **Visual realism vs physical fidelity.** A real-time particle system can look convincing
  without being a CFD smoke simulation. The scene must not imply operational fire prediction.
- **Sub-fragment spread is a model choice.** The fragment-level event log is authoritative;
  the per-tree front is an interpolation/refinement. The animation contract must say which
  layer a given pixel represents.
- **Scale.** A real VRI estate can contain millions of trees. Instancing, LOD, chunking, and
  a particle budget are mandatory. The first slice should target a few thousand trees.
- **Fuel data.** VRI polygons do not carry crown fuel or surface fuel. The synthetic fuel model
  is a calibration choice and must be visible in the scene manifest.
- **Browser GPU support.** WebGL2 is the baseline; WebGPU is optional. The standalone viewer
  should degrade to a simpler particle tier rather than fail.
- **Provenance and licensing.** Real VRI polygons and any external assets need a clear licence
  and a public-safe provenance record. The synthetic tree layer is labelled synthetic.
- **"Realistic" is a render target, not a claim.** The acceptance test is a frame-rate and
  visual-quality target plus a faithful event replay, not a comparison to a measured fire.

## 11. Non-goals

- Operational fire behaviour prediction or emergency response.
- A real-time CFD smoke solver in the browser.
- Replacing LANDIS-II, SpaDES, SELES, or a fire-physics model.
- Photoreal film VFX. The target is a convincing, interactive, auditable landscape view.
- A new growth model. The trees are a synthetic realization of the stand; the management
  model remains WS4's compiled dataset.
