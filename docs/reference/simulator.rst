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

A schedule is a CSV with the columns ``block_id,treatment,offset``, where ``offset`` is the number of
years after the start of the simulation (offset 0 is the first simulation year). The same block may be
scheduled more than once.

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
     - ``offset,account,value`` — the feature and product account values over the horizon, with a
       snapshot at offset -1 and one record per offset 0 to ``years - 1``; a period's products are
       summed per account.
   * - ``product_values.csv``
     - ``offset,account,value`` — the product yields recorded at each treatment (per event, before the
       per-account aggregation).
   * - ``dataset.json``
     - The dataset manifest, so a run records what it read.

When the simulator is given a road network (the Python API, ``Simulator.run(..., network=...)`` or
``route_model=...``), ``RouteCostLedger.write`` also writes ``route_values.csv``,
``network_table.csv``, ``route_table.<destination>.csv``, ``route_cost_report.csv``, and — when the
vertices table carries coordinates — ``used_roads.csv`` for the map overlay; see :doc:`roads`.

When the simulator is given a DHI account (``Simulator.run(..., dhi_account=...)`` or the
``--dhi-values`` and ``--dhi-metadata`` options), it also writes ``dhi_values.csv`` and
``dhi_metadata.json``; see :doc:`dhi`. ``ws4 report`` adds ``report_dhi.csv``.
When it is given a structure habitat account (``structure_habitat_account=...`` or
``--structure-values`` and ``--structure-metadata``), it writes
``structure_habitat_values.csv``, ``structure_habitat_landscape.csv``, and
``structure_habitat_metadata.json``; see :doc:`structure-habitat`. ``ws4 report`` adds
``report_structure_habitat.csv``.

When the simulator is given a block topology (``Simulator.run(..., topology_csv=...)``), it also
writes:

- ``patch_metrics.csv`` — per-year patch count, mean size, largest opening, and size-class
  distribution (see :doc:`spatial`);
- ``patch_accounts.csv`` — per-year patch accounts, when ``patch_accounts`` are given;
- ``edge_metrics.csv`` — per-year edge contrast accounts, when ``edge_elements`` are given;
- ``spread_metrics.csv`` — per-year spread-connectivity accounts, when ``spread_accounts`` and
  ``block_coordinates`` are given (see :doc:`spatial`);
- ``spread_membership.csv`` — the untreated blocks of every spread compartment, with the account,
  compartment index, area class, block area and component area, when the same inputs are given; the
  largest component is index 0;
- ``spatial_violations.csv`` — ``kind,year,area_ha,limit,block_a,block_b,years`` (``kind`` is
  ``opening``, ``green_up``, or ``core_area``), when a maximum opening size, a green-up interval, or
  a core-area rule is given.

Dataset integrity warnings
--------------------------

A compiled dataset can be internally inconsistent in a way that makes an account *wrong* rather than
missing. ``Simulator.from_dataset`` warns, naming the dataset and the affected labels, in two cases:

- **A repeated product row.** The product table is keyed by ``(track_id, treatment, label)`` and every
  row is recorded once per treated fragment, so two identical rows multiply the account. The builder
  now emits one row per key and curve; a dataset compiled before that rule carries the repeat and
  should be recompiled. A repeated key with *different* curves is a sum of components and is left
  alone.
- **An area-shaped product whose curve exceeds 1.0.** A label containing ``Area`` or ``Treated`` should
  yield a share of the block; a curve above 1.0 means the account is not hectares. This one is
  advisory: WS4 reports what the dataset says.

Neither warning changes a value. They exist so a multiplied account cannot pass as hectares.

API
---

.. autoclass:: ws4.sim.engine.Simulator
   :members:

.. autofunction:: ws4.sim.curve.curve_value
