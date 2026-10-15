Spatial structure and constraints
=================================

Space is part of the model, not a post-processing step (``notes/adr/0003``). The compiled matrix is
fragment-level; **blocks** are the runtime aggregate view that patch metrics and spatial constraints
operate on. Spatial structure enters through a **block topology**: an undirected adjacency edgelist
``src_block,dst_block,distance_m``.

Patch metrics
-------------

``ws4.patch.metrics`` groups the disturbed blocks of a year into connected patches over the topology
and reports:

- the patch count;
- the mean patch area;
- the largest opening (the maximum patch area);
- the size-class distribution (the default breaks are 5, 10, and 50 hectares).

The simulator writes these to ``patch_metrics.csv`` when it is given a topology:

.. code-block:: bash

   # Python API
   Simulator.from_dataset(dataset).run(schedule_csv, years, out_dir, topology_csv=topology)

Constraints
-----------

``ws4.patch.constraints`` reports two kinds of violation:

``opening_violations``
    Patches whose area exceeds a maximum opening size.
``green_up_violations``
    Adjacent blocks disturbed within a green-up interval.

``spatial_penalty`` combines them into a single penalty, and ``schedule_years`` splits a schedule into
per-year blocks and each block's first disturbance year. The simulator writes the violations to
``spatial_violations.csv``:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Column
     - Meaning
   * - ``kind``
     - ``opening`` or ``green_up``.
   * - ``year``
     - The year of the violation.
   * - ``area_ha``
     - The patch area (an opening violation), else 0.
   * - ``limit``
     - The violated limit (maximum opening area, or the green-up interval).
   * - ``block_a``, ``block_b``
     - The adjacent blocks (a green-up violation), else -1.
   * - ``years``
     - The gap between the two disturbances (a green-up violation), else 0.

Enforcement in the optimizer
----------------------------

The optimizer adds a weighted spatial penalty to its objective (``OptimizeConfig.spatial_weight``)
when a topology and a limit are given, so a searched schedule is pushed away from violations. The
penalty is disabled only by the explicit ``allow_spatial_override`` flag (``--spatial-override`` on
the command line).

API
---

.. autofunction:: ws4.patch.metrics.load_topology

.. autofunction:: ws4.patch.metrics.connected_patches

.. autofunction:: ws4.patch.metrics.patch_size_classes

.. autofunction:: ws4.patch.metrics.patch_metrics

.. autofunction:: ws4.patch.constraints.openings_by_year

.. autofunction:: ws4.patch.constraints.opening_violations

.. autofunction:: ws4.patch.constraints.green_up_violations

.. autofunction:: ws4.patch.constraints.spatial_penalty

.. autofunction:: ws4.patch.constraints.schedule_years
