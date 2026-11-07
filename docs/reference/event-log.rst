Event log and random tape
=========================

Purpose
-------

The ecosystem layer treats decisions and ecological processes as two sources of the same
event. A harvest is a controlled event; a fire is an uncontrolled one. Every event is
recorded in a deterministic log, and every stochastic draw is a pure function of a scenario
seed and a draw key. Together they make a stochastic landscape run exactly replayable and
let candidate schedules share the same random draws.

This page specifies the event record, the ordering key, the log format, the random tape, and
the replay contract. It does not yet specify process effects, cohort state, or scenario
aggregation; those are later P144 tasks.

Event record
------------

An event is one state transition at a known time and place:

.. list-table::
   :header-rows: 1
   :widths: 24 18 58

   * - Field
     - Type
     - Meaning
   * - ``event_id``
     - string
     - Stable identifier, unique within a log.
   * - ``scenario_id``
     - string
     - The scenario the event belongs to. The log header must name the same scenario.
   * - ``process_id``
     - string
     - The source that produced the event, such as ``fire`` or ``schedule``.
   * - ``event_type``
     - string
     - The event type, such as ``fire``, ``harvest``, or ``regeneration``.
   * - ``time``
     - number
     - Absolute simulation time in years. ``year`` must equal ``floor(time)``.
   * - ``year``
     - integer
     - The annual accounting year the event belongs to.
   * - ``phase``
     - string
     - The execution phase within the year.
   * - ``priority``
     - integer
     - Ordering priority within a phase; lower runs first.
   * - ``fragment_ids``
     - array of int
     - Fragments touched by the event.
   * - ``site_ids``
     - array of int
     - Sites touched by the event.
   * - ``block_ids``
     - array of int
     - Blocks touched by the event.
   * - ``severity_class``
     - string or null
     - Categorical severity, such as ``low`` or ``high``.
   * - ``severity_value``
     - number or null
     - Continuous severity in [0, 1].
   * - ``magnitude``
     - number or null
     - A process-specific magnitude, such as wind speed or mortality fraction.
   * - ``area_ha``
     - number or null
     - Event area in hectares.
   * - ``parent_event_id``
     - string or null
     - The event that caused this one, when the log is a causal chain.
   * - ``source``
     - string
     - Provenance identifier for the producer.
   * - ``confidence``
     - number or null
     - Confidence or detection probability in [0, 1].
   * - ``attributes``
     - object
     - Additional JSON-scalar attributes, sorted by key.

The canonical phases, in execution order, are ``forcing``, ``ignition``, ``propagation``,
``effect``, ``growth``, ``treatment``, ``regeneration``, and ``accounting``. A new phase is a
schema-version change, not a free label, because the phase is part of the execution order.

The ordering key is:

.. code-block:: text

   (time, phase rank, priority, spatial id, event id)

The spatial id is the smallest fragment, site, or block id the event names, or 0 when it
names none. The event id is the final tie-breaker. The order never depends on dictionary
insertion order or thread scheduling.

Compatibility
-------------

``Event.from_disturbance_row`` adapts the existing ``femic.disturbance.v1`` consumer row. The
row's ``source_id`` becomes ``process_id`` and ``source``, its ``year`` becomes ``time``, and
its phase is ``treatment`` for harvest and salvage and ``effect`` otherwise. The disturbance
loader and the ``ws4 disturbance`` command keep working unchanged.

Log format
----------

A log is one JSON object:

.. code-block:: text

   {
     "schema_version": "ws4.event-log.v1",
     "metadata": {
       "scenario_id": "base",
       "scenario_seed": 42,
       "tape_algorithm": "philox-2x64-v1",
       "package_hashes": {"fire": "<sha256>"},
       "attributes": {}
     },
     "events": [ ... ],
     "event_digest": "<sha256>"
   }

The digest covers the metadata and the ordered events. Reading a log validates the schema
version, the closed top-level field set, the event records, the scenario identity, the
ordering, the uniqueness of event ids, and the digest. A mismatch fails with an
``EventError`` rather than returning a partially valid log.

Random tape
-----------

Every primitive draw is a pure function of:

.. code-block:: text

   (scenario seed, process id, spatial unit id, year, draw index)

The tape uses a counter-based generator (Philox 2x64). There is no global generator and no
call-order dependence. Two consequences matter for the optimizer:

- **Common random numbers.** Two candidate schedules that ask for the same key receive the
  same draw. Differences between candidates are due to decisions, not noise.
- **Deterministic parallelism.** Each spatial unit draws from its own stream, so a worker's
  order does not change the result.

A caller that needs several scalar draws for one unit-year increments ``draw_index``. A
caller that needs a vector uses ``size``; the vector is drawn from the same counter block.

Replay
------

``EventLog.verify_replay`` takes a runner from metadata to events. It rebuilds the log and
requires the same ordered event sequence. A changed event, a missing event, an extra event,
or a different scenario raises ``ReplayError``. The runner is the process engine in a later
task; this page fixes the contract it must satisfy.

Command
-------

.. code-block:: bash

   ws4 ecosystem validate-log --events runs/base/events.json
   ws4 ecosystem validate-log --events runs/base/events.json --json

The text report shows the scenario, seed, event count, year range, area, processes, event
types, and replay digest. ``--json`` emits the same summary as a stable JSON object.

Limits
------

- The command validates the log, not the dataset it refers to. Referential integrity against
  fragments, sites, blocks, and the horizon is a later task.
- No process is executed yet. The log is a record and a replay contract, not a fire model.
- The random tape is one algorithm. A stored log that names another algorithm is rejected
  rather than silently replayed with the wrong generator.
- The event record is a superset of the disturbance row, not a replacement for the FEMIC
  contract.

Cross-references
----------------

- :doc:`compiled-dataset`
- :doc:`simulator`
- :doc:`disturbance`
- :doc:`carbon`
