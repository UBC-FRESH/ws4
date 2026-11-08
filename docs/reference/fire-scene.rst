Fire scene and event-driven visuals
===================================

The optional ``ws4.scene`` package compiles a completed P144 fire run and a synthetic
individual-tree inventory into a portable scene directory. The event log remains the
authority for the fragment-level outcome; the scene adds a per-tree ignition schedule and a
standalone viewer.

Compile a scene
---------------

.. code-block:: python

   from ws4.scene import compile_fire_scene, synthetic_tree_inventory

   trees = synthetic_tree_inventory(result.state.fragment_areas, seed=11)
   scene = compile_fire_scene(result, trees, scene_id="demo")
   paths = scene.write("runtime/fire-scene")

The writer produces ``manifest.json``, ``trees.parquet``, ``stands.parquet``, ``fires.csv``,
``animation.parquet``, ``event_log.json``, ``summary.json``, and a self-contained
``viewer.html``. The viewer data is embedded in the HTML; no server is required.

Behaviour-driven flames and smoke
---------------------------------

When a fire event carries the FBP behaviour attributes from
``ws4.ecosystem.fire.FireBehaviourConfig``, the scene reads them directly:

- ``flame_length_m`` scales the per-tree flame intensity;
- ``smoke_strength`` scales the smoke contribution;
- ``head_fire_intensity_kw_m``, ``ros_m_min``, and ``crown_fraction_burned`` are retained on
  the fire-event table.

If those attributes are absent (the legacy graph path), the scene keeps its deterministic
stand-in values. The viewer does not invent a fire-behaviour result.

The scene is a run artifact. It does not change the compiled dataset, the ecosystem package,
or the event log.
