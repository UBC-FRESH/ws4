# Generic process executor

Status: implemented (P179)
Phase: P179 (#1056)
Date: 2026-11-12
Related: `notes/design/ws4-stochastic-landscape.md`,
`ws4/ecosystem/process.py`, `ws4/ecosystem/executor.py`, `ws4/ecosystem/fire.py`

## 1. Why this exists

P144 proved the event, tape, package, cohort, scenario, and fire contracts. Its runner was
still fire-shaped: `FireRun` called `FireProcess` and `SalvageSource` directly. That is enough
for one vertical slice, not for a landscape engine with succession, wind, insects, drought,
and management policies.

P179 introduces the missing seam:

```text
one state + many sources + one executor + one event log
```

The executor does not know what a process means. It knows phases, event ownership, stable
ordering, and state transitions.

## 2. Process contract

A source declares:

- `process_id`: the owner of the events it emits;
- `phases`: a non-empty subset of `EVENT_PHASES`;
- `state_reads` and `state_writes`: declared state-variable names;
- `events(state, context)`: a batch of events for the current phase;
- `apply(state, event)`: the state transition for one owned event.

`Process` is an uncontrolled source. `DecisionSource` is the controlled variant. The executor
treats both the same way; the distinction is for provenance and future policy search.

`ProcessContext` carries the year, phase, scenario id, prior-year history, and the events
already emitted in the current year. A source can use the history for cross-phase dependencies
such as salvage after fire.

## 3. Executor semantics

For each year and each phase in `EVENT_PHASES`:

1. Ask every source participating in the phase for a batch.
2. Reject an event with the wrong owner, year, phase, or scenario.
3. Sort the batch by the canonical event key.
4. Apply each event through its owning source and update the state.
5. Ask again until every source emits no more events.

The repeat-until-empty rule matters. It lets a source see the state left by its previous batch.
Fire uses it to propagate one ignition at a time, so a later ignition sees fuel removed by an
earlier fire instead of a stale batch snapshot.

The executor writes the existing `EventLogBuilder`. Events are logged in canonical order at the
end of the year; application order can differ from log order, but replay is over the sorted log.

## 4. Fire and salvage

`FireProcessSource` adapts `FireProcess`:

- `ignition` phase emits ignitions that are not already in the year log;
- `propagation` phase emits one ignition's spread batch, then the executor applies it and asks
  again;
- a start fragment already burned this year is skipped;
- `apply` delegates to the existing fire effect.

`SalvageProcessSource` adapts `SalvageSource` in the `treatment` phase and reads fire events
from the context history and current year.

`FireRun` now builds these two sources and calls the generic executor. Its public `FireResult`
and account behavior are unchanged.

## 5. Validation

The tests cover:

- context validation for year, phase, and scenario;
- process declaration validation and duplicate ids;
- two sources in one phase applied in event-key order;
- exact replay across two identical executor runs;
- rejection of a foreign event owner;
- fire, a synthetic mutating process, and salvage in one executor run;
- the existing fire event-log and account tests through `FireRun`.

## 6. Limits

- Sources in the same phase are asked in declaration order; a future phase may need a global
  dependency-aware scheduler. The current batch merge and canonical sort preserve event order
  within each batch.
- State read/write declarations are validated as names, not yet enforced as exclusive ownership.
  Fire and salvage share `snag_t_ha` by design.
- The executor is annual. Continuous-time scheduling and a raster site layer are later work.
- The synthetic process is a test source, not a production ecological model.
