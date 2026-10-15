Simulator
=========

The simulator replays a treatment schedule over a compiled dataset and writes a run directory. It
reads only the compiled dataset (see :doc:`compiled-dataset`), and it is deterministic given a
schedule: the same dataset and schedule produce the same account values.

Model
-----

The simulator advances one year at a time. Each fragment ages by one year per step. A fragment's
``track_id`` gives its trajectory, and its ``offset`` is its position on that track; the account
values for a year are the area times the feature curve evaluated at the offset.

A treatment in the schedule applies to a block only when the block's track offers that treatment at
the block's current offset (the Model II rule). Applying a treatment:

- records the product yields (area times each product curve at the pre-treatment offset);
- resets the fragment's ``track_id`` to the treatment's ``new_track`` and its ``offset`` to the
  treatment's ``offset``.

A treatment the track does not offer is a no-op. See ``notes/adr/0005``.

Schedule
--------

A schedule is a CSV with the columns ``block_id,treatment,period``, where ``period`` is a year. The
same block may be scheduled more than once.

.. code-block:: bash

   ws4 simulate --dataset build/compiled --schedule schedule.csv --years 30 --out run

Outputs
-------

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - File
     - Contents
   * - ``account_values.csv``
     - ``year,account,value`` — the feature account values over the horizon.
   * - ``product_values.csv``
     - ``year,account,value`` — the product yields recorded at each treatment.
   * - ``dataset.json``
     - The dataset manifest, so a run records what it read.

When the simulator is given a road network (the Python API, ``Simulator.run(..., network=...)``), it
also writes:

- ``route_values.csv`` — ``year,block_id,dest_id,product,volume,length_m,cost``, each produced product
  routed to the block's nearest destination (see :doc:`roads`).

When the simulator is given a block topology (``Simulator.run(..., topology_csv=...)``), it also
writes:

- ``patch_metrics.csv`` — per-year patch count, mean size, largest opening, and size-class
  distribution (see :doc:`spatial`);
- ``spatial_violations.csv`` — ``kind,year,area_ha,limit,block_a,block_b,years``, when a maximum
  opening size or a green-up interval is given.

API
---

.. autoclass:: ws4.sim.engine.Simulator
   :members:

.. autofunction:: ws4.sim.curve.curve_value
