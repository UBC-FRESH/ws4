Process executor
================

Purpose
-------

``ws4.ecosystem.executor`` is the generic annual loop for the stochastic landscape engine.
It runs one or more event sources over one ``CohortState``, orders their events, applies each
event through its owner, and writes the existing replayable event log. It does not know what
fire, salvage, succession, or a synthetic test process means.

The P144 fire slice used a dedicated ``FireRun`` loop. P179 moves the loop behind the generic
executor; fire and salvage are now sources, not the executor's identity.

Process contract
----------------

A source declares:

- ``process_id`` — the owner of its events;
- ``phases`` — a non-empty subset of ``EVENT_PHASES``;
- ``state_reads`` and ``state_writes`` — the state variables it declares;
- ``events(state, context)`` — the next batch of events for the current phase;
- ``apply(state, event)`` — the transition for one owned event.

``ws4.ecosystem.process.Process`` is the uncontrolled protocol and ``DecisionSource`` is the
controlled protocol. ``ProcessContext`` carries the year, phase, scenario id, prior-year
history, and current-year events.

Execution
---------

For each year and phase, the executor:

1. asks every participating source for a batch;
2. rejects an event with the wrong owner, year, phase, or scenario;
3. sorts the batch by the canonical event key;
4. applies each event through its owning source;
5. asks again until no source emits more events.

The repeat-until-empty rule lets a source see the state left by its previous batch. Fire uses
it to propagate one ignition at a time.

Fire and salvage
----------------

``FireProcessSource`` emits ignitions in the ``ignition`` phase and one ignition's spread batch
in the ``propagation`` phase. ``SalvageProcessSource`` emits in the ``treatment`` phase and reads
fire events from the context.

``FireRun`` builds these two sources and calls ``Executor``. Its public result, event log, and
accounts are unchanged.

Limits
------

- The executor is annual, not continuous time.
- State declarations are checked as names, not enforced as exclusive ownership; fire and
  salvage share the snag variable by design.
- Same-phase sources are asked in declaration order; the batch is canonically sorted.
- The synthetic process used in tests is not a production ecological model.
