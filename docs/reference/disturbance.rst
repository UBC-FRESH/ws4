Disturbance events
==================

Purpose
-------

WS4 consumes the ``femic.disturbance.v1`` event table as a read-only report.
The loader accepts the flat consumer rows produced by FEMIC (or the full event
records) and reports what happened, where, when, and how severe it was.

This page does not make disturbances part of the simulation. Applying events to
growth, transitions, or the objective is a later phase.

Consumer row
------------

The loader reads these fields:

.. list-table::
   :header-rows: 1
   :widths: 28 16 56

   * - Field
     - Type
     - Meaning
   * - ``event_id``
     - string
     - Stable event identifier, unique within the table.
   * - ``event_type``
     - string
     - ``fire``, ``insect``, ``disease``, ``drought``, ``wind``, ``flood``,
       ``partial_mortality``, ``harvest``, ``salvage``, or ``other``.
   * - ``year``
     - integer
     - Calendar year the event began, 1900-2300.
   * - ``severity_class``
     - string
     - ``low``, ``moderate``, ``high``, ``very_high``, or ``unknown``.
   * - ``confidence``
     - number
     - Confidence in [0, 1].
   * - ``source_id``
     - string
     - Upstream source identifier.
   * - ``severity_value``
     - number or null
     - Optional continuous severity in [0, 1].
   * - ``fragment_ids``
     - array or null
     - FEMIC fragment ids.
   * - ``block_ids``
     - array or null
     - WS4 block ids.
   * - ``area_ha``
     - number or null
     - Event area in hectares.

A full ``femic.disturbance.v1`` record is also accepted; fields WS4 does not
need (geometry, attribution, notes, timestamps) are ignored. The file may be a
JSON list, an object with an ``events`` list, or a single event object.

Command
-------

.. code-block:: bash

   ws4 disturbance --events data/disturbance/fire_2023.json
   ws4 disturbance --events data/disturbance/fire_2023.json --json
   ws4 disturbance --events data/disturbance/table.json --block-id 101

The text report lists each event's id, year, type, severity, blocks, and area.
``--json`` emits a stable summary with:

- ``event_count``
- ``event_types``
- ``severity_classes``
- ``year_min`` and ``year_max``
- ``total_area_ha``
- ``affected_blocks``
- ``affected_fragments``
- ``sources``
- ``confidence_min`` and ``confidence_max``

Limits
------

- The loader does not apply events to the compiled dataset or the model.
- ``--block-id`` matches ``block_ids`` directly. Fragment-to-block resolution
  belongs to the caller.
- Geometry is not validated; the FEMIC contract owns that shallow check.
- The command does not write a run directory or modify a schedule.

Cross-references
----------------

- :doc:`compiled-dataset`
- :doc:`simulator`
- :doc:`femic-lidar`
