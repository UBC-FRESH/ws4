Fire scene and synthetic trees
==============================

Purpose
-------

The fire scene turns a P144 fire run and a synthetic individual-tree inventory into a
portable 3D package: a tree table, stand squares, fire events, a per-tree ignition schedule, a
manifest, and a standalone viewer. The scene is a run artifact. It does not change the
compiled dataset, the ecosystem package, or the event log.

The tree layer is synthetic. The polygons and the fire event log are the authoritative
pieces. Every scene manifest says so. Real VRI polygons can replace the built-in square
footprints through the Nemora adapter.

Tree inventory
--------------

``ws4.tree.inventory.v1`` is a table with one row per tree:

.. list-table::
   :header-rows: 1
   :widths: 24 16 60

   * - Column
     - Type
     - Meaning
   * - ``tree_id``
     - string
     - Stable id within the scene.
   * - ``fragment_id``
     - integer
     - The WS4 fragment the tree belongs to.
   * - ``x``, ``y``, ``z``
     - number
     - Scene coordinates in metres. ``z`` is the ground elevation.
   * - ``species``
     - string
     - Species label.
   * - ``dbh_cm``
     - number
     - Diameter at breast height.
   * - ``height_m``
     - number
     - Total height.
   * - ``crown_ratio``
     - number
     - Live crown length divided by height, in [0, 1].
   * - ``crown_radius_m``
     - number
     - Crown radius.
   * - ``live``
     - boolean
     - Live or dead at scene start.
   * - ``decay_class``
     - integer
     - Dead-wood decay class, 0 for live.
   * - ``crown_fuel_t``
     - number
     - Crown fuel mass in tonnes.
   * - ``surface_fuel_t_ha``
     - number
     - Local surface fuel load.
   * - ``snag_t``
     - number
     - Standing dead mass in tonnes.
   * - ``provenance``
     - string
     - Generator provenance label.

The built-in generator places trees uniformly inside each fragment's synthetic square, draws
a lognormal DBH, derives height and crown size from DBH, and assigns a crown fuel mass. A
fragment is a square whose side is ``sqrt(area_ha * 10000)`` metres; the fragments are laid out
in a near-square grid unless explicit origins are supplied. The generator is seeded per
fragment, so the same area map and seed reproduce the same tree table.

``TreeInventory`` also carries optional ``fragment_polygons``. When present, each fragment
has a real exterior ring and ``bounds_violations`` checks the polygon, not a square.

Nemora adapter
--------------

``ws4.scene.nemora`` adapts a Nemora tree table without importing Nemora at runtime:

- ``load_vri_polygons`` reads a GeoJSON FeatureCollection and keeps each Polygon or the
  largest part of a MultiPolygon;
- ``load_nemora_tree_table`` reads CSV or Parquet and normalizes aliases such as ``dbh`` to
  ``dbh_cm`` and ``height`` to ``height_m``;
- ``trees_from_nemora`` places every tree in its VRI polygon, either from an explicit
  ``fragment_id`` or by point-in-polygon, and raises if the assignment is missing or
  ambiguous;
- ``load_nemora_scene`` is the file-level entry point.

The inventory source records the adapter version, Nemora version, seed, polygon source, and
CRS. Missing fuel columns get documented defaults: crown fuel is ``0.2 × biomass`` when
biomass exists, otherwise ``0.0015 × DBH²``; surface fuel defaults to 10 t/ha; snag load
defaults to zero. These are placeholders, not a calibrated fuel model.

The adapter is thin on purpose. Nemora's API is external and may change; WS4 reads the
exported table and keeps the contract at the file boundary.

Scene package
-------------

``ws4.fire.scene.v1`` writes:

.. code-block:: text

   fire_scene/
     manifest.json        # schema, seed, replay digest, counts, synthetic flag
     trees.parquet        # the tree inventory
     stands.parquet       # fragment polygons, area, origin, burn time
     fires.csv            # the fire events used by the viewer
     animation.parquet    # per-tree ignition, burn duration, intensity, state
     event_log.json       # the full P144 event log
     summary.json         # counts, tree summary, timeline end
     payload.json         # compact bounds/stands/trees/fires/timeline payload
     viewer.html          # standalone viewer with the scene data embedded

The manifest records the fire run's replay digest, the scenario, the tree generator, the
seed, the particle budget, the burn duration, and the scene time unit. The animation can use
the fragment event time or a P156 growth field sampled at each tree position. With the growth
field, each tree gets its own cell arrival time and the front moves continuously through the
stand. The event log remains the authority for the fragment-level outcome.

The scene clock defaults to years for the annual P144 event path. A growth-driven scene can
set ``time_unit="minutes"``; the demo uses minutes since ignition, a two-minute tree burn,
and a timeline of about 122 minutes.

Viewer
------

``viewer.html`` is a standalone page. It embeds the scene JSON, so it opens from a local file
without a server. It uses Three.js from a CDN, so the first slice needs internet access for
the module.

Web workspace
-------------

The WS4 web service discovers a completed scene in a run directory when it contains
``fire_scene/manifest.json`` (or ``fire-scene``, ``fire``, or ``scene``) with schema
version ``ws4.fire.scene.v1``. The read-only endpoints are:

- ``GET /api/fire/scenes``: discovered scenes and manifest summaries;
- ``GET /api/fire/runs/{run}``: one scene manifest and summary;
- ``GET /api/fire/runs/{run}/payload``: the compact viewer payload from
  ``payload.json``;
- ``GET /api/fire/runs/{run}/viewer``: the viewer with the vendored Three.js paths.

The **Fire** workspace shows the scene over the main canvas, with a shared timeline,
play/pause, speed, camera controls, tree and fragment inspection, and side-by-side Scene A
and Scene B comparison. The viewer accepts ``?embedded=1`` and a small ``postMessage`` API
so the workspace timeline can drive both scenes. The standalone viewer keeps its CDN
module import; the served web viewer uses the local vendored Three.js module.

The viewer provides:

- an orbit camera over the landscape;
- instanced trees with species colours and a live/burnt state;
- a Play/Pause timeline with speed control and a scrubber;
- procedural flame and smoke particles;
- a fire light and a burnt-scar overlay on the stands;
- a Focus fire button that frames the active front;
- tree/fragment counts and a burning/burnt readout.

The viewer is a visual prototype, not a calibrated fire-behaviour model. The flames and
smoke are procedural; flame intensity and smoke scale with the local P156 directional ROS
when a growth field is supplied. The burn duration is a scene parameter.

Example
-------

.. code-block:: bash

   python examples/fire_3d_demo.py

The script builds a synthetic landscape, runs the P156 FBP growth field, samples the field at
22,500 tree positions, and writes ``tmp/fire-3d-demo/viewer.html``. Open that file in a
browser with WebGL2.

Programmatically:

.. code-block:: python

   from ws4.scene import load_nemora_scene, sample_tree_ignition

   trees = load_nemora_scene(
       "nemora_trees.csv",
       "vri_polygons.geojson",
       seed=7,
       source="public-vri",
       crs="EPSG:3005",
       nemora_version="0.3.0",
   )
   animation = sample_tree_ignition(trees, growth, cell_size_m=5.0, burn_duration=2.0)

Real VRI cluster
----------------

.. code-block:: bash

   python examples/fire_3d_vri_demo.py

The VRI demo uses a 12-polygon cluster from the public TSA 24 block geometry in
``examples/fire_scene_vri``. The polygons are translated to a local origin and populated with
12,588 Nemora-placed synthetic stems at 120 stems/ha. The growth grid is masked to the
polygons, so the fire front follows the real stand shapes instead of a square grid.

The current result is 95.42 ha burned, 27.07 m/min head ROS, 8.40 m flame length, and a
0–240 minute ignition window. The manifest records the VRI source, the Nemora adapter version,
the seed, and the synthetic-tree flag.

Validation
----------

- The same areas and seed reproduce the same tree table and scene.
- Every generated tree lies inside its fragment square or VRI polygon.
- A tree outside its VRI polygon raises an adapter error.
- The Nemora adapter records the adapter version, Nemora version, seed, polygon source, and
  CRS.
- A growth-driven scene samples the cell arrival time at each tree and reports per-tree
  ignition times.
- The tree summary reports stems per hectare, basal area, and mean size.
- Every animated ignition maps to a fire event; the manifest carries the event-log replay
  digest.
- The scene package writes every listed file and the viewer opens without a JavaScript error.
- The visual check is manual: play the timeline and confirm the fire front, flames, smoke,
  burnt scar, and post-fire tree state.

Current limits
--------------

- The tree layer is synthetic and is not a VRI inventory measurement.
- The built-in generator uses square fragment footprints. The Nemora adapter accepts real VRI
  polygons, but the tree allometry and fuel defaults are placeholders, not a calibration.
- Flames and smoke are a first procedural pass. Shader quality, embers, heat haze, and LOD are
  P155.3.
- The viewer uses a CDN for Three.js. The WS4 web Fire workspace and a vendored module are
  P155.4.
- The burn duration, intensities, and particle counts are scene parameters, not a fire
  physics calibration.

Cross-references
----------------

- :doc:`ecosystem-fire`
- :doc:`ecosystem-scenarios`
- :doc:`ecosystem-package`
- :doc:`../concepts/the-simulation`
