Fire scene and synthetic trees
==============================

Purpose
-------

The fire scene turns a P144 fire run and a synthetic individual-tree inventory into a
portable 3D package: a tree table, stand squares, fire events, a per-tree ignition schedule, a
manifest, and a standalone viewer. The scene is a run artifact. It does not change the
compiled dataset, the ecosystem package, or the event log.

The tree layer is synthetic. The polygons and the fire event log are the authoritative
pieces. Every scene manifest says so.

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

Scene package
-------------

``ws4.fire.scene.v1`` writes:

.. code-block:: text

   fire_scene/
     manifest.json        # schema, seed, replay digest, counts, synthetic flag
     trees.parquet        # the tree inventory
     stands.parquet       # fragment squares, area, origin, burn time
     fires.csv            # the fire events used by the viewer
     animation.parquet    # per-tree ignition, burn duration, intensity, state
     event_log.json       # the full P144 event log
     summary.json         # counts, tree summary, timeline end
     viewer.html          # standalone viewer with the scene data embedded

The manifest records the fire run's replay digest, the scenario, the tree generator, the
seed, the particle budget, and the burn duration. The animation is derived from the fire
events: a tree's ignition time is the earliest fire event for its fragment; the burn duration
and visual intensities come from the scene parameters and the tree's fuel. The event log
remains the authority for the fragment-level outcome.

Viewer
------

``viewer.html`` is a standalone page. It embeds the scene JSON, so it opens from a local file
without a server. It uses Three.js from a CDN, so the first slice needs internet access for
the module; the later web phase will vendor the module.

The viewer provides:

- an orbit camera over the landscape;
- instanced trees with species colours and a live/burnt state;
- a Play/Pause timeline with speed control and a scrubber;
- procedural flame and smoke particles;
- a fire light and a burnt-scar overlay on the stands;
- a Focus fire button that frames the active front;
- tree/fragment counts and a burning/burnt readout.

The first slice is a visual prototype, not a calibrated fire-behaviour model. The flames and
smoke are procedural and the burn duration is a scene parameter, not a physical prediction.

Example
-------

.. code-block:: bash

   python examples/fire_3d_demo.py

The script builds a 3×3 synthetic landscape, runs a P144 fire, generates 22,500 trees, and
writes ``tmp/fire-3d-demo/viewer.html``. Open that file in a browser with WebGL2.

Programmatically:

.. code-block:: python

   from ws4.ecosystem.fire import FireConfig, FireRun, synthetic_grid
   from ws4.scene import compile_fire_scene, synthetic_tree_inventory

   _, state, edges = synthetic_grid(3, 3)
   fire = FireRun(state, edges, FireConfig(ignition_rate_per_fragment_year=0.08), seed=7).run(15)
   trees = synthetic_tree_inventory(fire.state.fragment_areas, seed=7, trees_per_ha=250)
   scene = compile_fire_scene(fire, trees, burn_duration_years=1.5)
   scene.write("tmp/fire-scene")

Validation
----------

- The same areas and seed reproduce the same tree table and scene.
- Every generated tree lies inside its fragment square.
- The tree summary reports stems per hectare, basal area, and mean size.
- Every animated ignition maps to a fire event; the manifest carries the event-log replay
  digest.
- The scene package writes every listed file and the viewer opens without a JavaScript error.
- The visual check is manual: play the timeline and confirm the fire front, flames, smoke,
  burnt scar, and post-fire tree state.

Current limits
--------------

- The tree layer is synthetic and is not a VRI inventory measurement.
- The built-in generator uses square fragment footprints. The Nemora/VRI producer and real
  polygon containment are P150.2.
- Flames and smoke are a first procedural pass. Shader quality, embers, heat haze, and LOD are
  P150.3.
- The viewer uses a CDN for Three.js. The WS4 web Fire workspace and a vendored module are
  P150.4.
- The burn duration, intensities, and particle counts are scene parameters, not a fire
  physics calibration.

Cross-references
----------------

- :doc:`ecosystem-fire`
- :doc:`ecosystem-scenarios`
- :doc:`ecosystem-package`
- :doc:`../concepts/the-simulation`
