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

Patch accounts
--------------

A **patch account** describes the size distribution of connected patches over the topology, for a
patch **criteria** attribute and a threshold (``ws4.patch.accounts``). A block joins a patch when
its criterion value exceeds the threshold, and its contribution to the patch area is the criterion
value times its block area (a half disturbed block contributes half its area). For each size class
the account reports five sub-accounts:

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Sub-account
     - Meaning
   * - ``area``
     - The patch area in the size class, in hectares.
   * - ``size``
     - The area in the class as a percentage of the total patch area.
   * - ``shape``
     - The mean compactness of the patches in the class, 0 to 100 (100 is a circle).
   * - ``frequency``
     - The number of patches in the class.
   * - ``attractor``
     - A flag that draws the average patch size toward the class; its value mimics ``size``.

The criteria value per block comes from a feature curve (``Simulator.block_criteria``), so the
patch membership changes over time as stands age and are treated. When a topology and patch
accounts are given, the simulator writes ``patch_accounts.csv`` with one row per period.

.. code-block:: python

   from ws4.patch.accounts import PatchAccount

   account = PatchAccount(name="patch.disturbance", criteria="feature.Seral.young", threshold=0.5)
   Simulator.from_dataset(dataset).run(
       schedule, years, out_dir, topology_csv=topology, patch_accounts=[account]
   )

The topology loader (``load_patch_edges``) accepts the established columns
(``BLOCK1,BLOCK2,DISTANCE,LENGTH``) and drops the ``-9999`` boundary sentinel, as well as the WS4
columns (``src_block,dst_block,distance_m``).

Constraints
-----------

``ws4.patch.constraints`` reports two kinds of violation:

``opening_violations``
    Patches whose area exceeds a maximum opening size.
``green_up_violations``
    Adjacent blocks disturbed within a green-up interval.
``core_area_violations``
    Patches whose **core area** is below a minimum (see below).

``spatial_penalty`` combines them into a single penalty, and ``schedule_years`` splits a schedule into
per-year blocks and each block's first disturbance year. The simulator writes the violations to
``spatial_violations.csv``:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Column
     - Meaning
   * - ``kind``
     - ``opening``, ``green_up``, or ``core_area``.
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

Core-area rule
--------------

A **core-area rule** requires interior habitat, not just disturbed area. The core area of a patch
removes a strip of ``buffer_m`` metres around its perimeter
(``core = area - perimeter * buffer + pi * buffer**2``, clipped at zero), so a patch of the same area
with a longer, more dendritic edge has less core. ``core_area_violations`` reports each patch whose
core is below ``min_core_area_ha``; the optimizer adds the shortfall to its penalty
(``OptimizeConfig.core_buffer_m`` / ``min_core_area_ha`` or ``--core-buffer-m`` /
``--min-core-area-ha``).

Edge contrast
-------------

An **edge contrast** account measures the juxtaposition of one forest type beside another (the
established edge-target API). For each shared edge it takes the boundary where one side matches the
first attribute and the other matches the second, weighted by the per-unit values and the shared edge
length, and sums it into a named account:

.. code-block:: bash

   # edges.csv
   account,attribute1,attribute2,factor
   feature.Edge.OldYoung,feature.Seral.old,feature.Seral.young,1

Adjacent blocks of the same type contribute nothing; a hard boundary between two contrasting types
contributes the shared edge length. The per-block attribute values come from feature curves
(``Simulator.block_criteria``), so the account changes over time. The simulator writes
``edge_metrics.csv`` and adds the edge accounts to ``account_values.csv`` (so the optimizer can target
them, for example a minimum on ``feature.Edge.OldYoung``). ``load_edge_elements`` loads the
specifications from CSV.

Spread connectivity
-------------------

A **spread-connectivity account** measures how fragmented the fuel body a fire could run through is
(``ws4.spread.accounts``). It exists because the patch accounts can point the wrong way: on the TSA23
bridge instance a wind-perpendicular barrier burned least of three equal-area patterns while having the
*largest* large-patch share. A patch target penalizes the arrangement that works.

The account needs a **block topology** and a table of **block coordinates** (``block,x,y``, in metres),
because the topology carries distances but no bearings. Each account names a criterion, a **bearing**
(degrees clockwise from north — the direction the fire travels, which is the wind direction) and a
**tolerance**. An edge lying within the tolerance of the bearing and no longer than ``search_distance``
is *fast*; a treated block transmits nothing. The fast edges are then traversed as an **undirected**
graph: a fire goes around an obstacle as well as through it, so what confines it is the connected fuel
body, not a one-way corridor.

.. code-block:: yaml

   # spread.yaml
   accounts:
     - name: spread.ft
       criteria: product.Treated.managed.FT
       bearing: 225
       tolerance: 60
       search_distance: null

Two sub-accounts, both lower-is-better and both in hectares:

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Sub-account
     - Meaning
   * - ``largest_component``
     - The area of the largest connected set of untreated blocks over the fast edges: the fuel body a
       fire can wander through from one ignition.
   * - ``percolation_reach``
     - The area-weighted mean compartment area, ``sum(area**2) / sum(area)``: what a random hectare
       sees.

The account also reports ``TOTAL.area`` and ``TOTAL.blocks`` for the untreated set. The landscape is
every block with a coordinate, not only the blocks the criterion mentions: a *product* criterion holds
only the blocks that produced in the period, and every other block is untreated fuel.

.. code-block:: python

   from ws4.spread.accounts import SpreadAccount

   account = SpreadAccount(
       name="spread.ft", criteria="product.Treated.managed.FT", bearing=225, tolerance=60
   )
   Simulator.from_dataset(dataset).run(
       schedule,
       years,
       out_dir,
       topology_csv=topology,
       spread_accounts=[account],
       block_coordinates=coordinates,
   )

**What the measure can and cannot say.** Direction lives in the cone (which edges are fast), not in the
traversal. A full-span band along the wind fragments the fuel body just as much as one across it, which
the synthetic oracle pins deliberately. Separating those two needs anisotropic spread rates and a burn
duration — a fire model, not an account.

On the TSA23 bridge instance the largest compartment orders the three equal-area patterns as the fire
model did at its original 177,088 ha treatment (82,874 / 105,020 / 196,767 ha against 19,640 / 19,870 /
20,298 ha burned). **That comparison does not survive a matched footprint.** When the fire model is run
on the ~54,000 ha WS4 can actually treat, the ranking flips across seeds and the largest mean gap
(0.38%) is far inside the seed noise (15%). The account is therefore a fragmentation measure with **no
demonstrated relationship** to this fire model at the intervention WS4 can represent; the report is
`notes/reports/p16-bridge-matched.md`. A bounded, 20%-treated study footprint does not restore the
ordering either: there the largest compartment reads 23 / 94 / 6 ha at a 60° cone and 49 / 105 / 10 ha
at 90° (barrier / clumped / random), so no cone width produces barrier < clumped < random. The
ordering of the compartment itself holds from a 60° to a 90°
cone, with a magnitude that depends on how near the cone sits to the percolation threshold.

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

.. autofunction:: ws4.patch.constraints.core_area_violations

.. autofunction:: ws4.patch.constraints.core_area_penalty

.. autofunction:: ws4.patch.constraints.edge_contrast

.. autofunction:: ws4.patch.constraints.schedule_years

.. autofunction:: ws4.patch.metrics.core_area

.. autofunction:: ws4.patch.metrics.patch_core_areas

.. autofunction:: ws4.patch.metrics.patch_perimeter

.. autofunction:: ws4.patch.edge.load_edge_elements

.. autofunction:: ws4.patch.edge.edge_values

.. autoclass:: ws4.patch.edge.EdgeElement
   :members:

.. autofunction:: ws4.patch.accounts.load_patch_edges

.. autofunction:: ws4.patch.accounts.size_class_labels

.. autofunction:: ws4.patch.accounts.patch_account_values

.. autoclass:: ws4.patch.accounts.PatchAccount
   :members:

.. autoclass:: ws4.patch.accounts.PatchLedger
   :members:

.. autoclass:: ws4.spread.accounts.SpreadAccount
   :members:

.. autofunction:: ws4.spread.accounts.spread_account_values

.. autofunction:: ws4.spread.accounts.transmitting_edges

.. autofunction:: ws4.spread.accounts.load_spread_accounts

.. autofunction:: ws4.spread.accounts.load_block_coordinates
