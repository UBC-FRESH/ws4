"""The generic multi-process executor for the stochastic landscape engine.

The executor owns the annual loop. In each year it walks the canonical event phases, asks every
source that participates in a phase for a batch of events, orders that batch by the canonical
event key, and applies each event through the source that owns it. A source is called again
until it emits no more events, so state changes are visible to its next batch.

The executor does not know what a fire, salvage, succession, or synthetic test process means.
It only knows the process protocol in :mod:`ws4.ecosystem.process`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

from .events import EVENT_PHASES, Event
from .log import EventLog, EventLogBuilder, EventLogMetadata
from .process import (
    DecisionSource,
    Process,
    ProcessContext,
    ProcessError,
    validate_sources,
)
from .state import CohortState

#: The maximum number of batches one source may emit in one phase.
MAX_BATCHES_PER_PHASE: Final[int] = 10_000

EventHook = Callable[[Event, CohortState, CohortState], None]
YearHook = Callable[[int, CohortState, Sequence[Event]], None]


@dataclass(frozen=True)
class ExecutionResult:
    """The final state and event log of one multi-process run.

    Parameters
    ----------
    state : CohortState
        The final cohort state.
    log : EventLog
        The replayable event log.
    events : tuple of Event
        The events in log order.
    """

    state: CohortState
    log: EventLog
    events: tuple[Event, ...]


class Executor:
    """Run multiple process and decision sources over one cohort state.

    Parameters
    ----------
    state : CohortState
        The initial state.
    sources : sequence of Process or DecisionSource
        The event sources, in declaration order. Process ids must be unique.
    metadata : EventLogMetadata
        The event-log header.
    on_event : callable or None, optional
        Called with ``(event, before, after)`` after every applied event.
    on_year : callable or None, optional
        Called with ``(year, state, events)`` after the year's events are applied and sorted.
    """

    def __init__(
        self,
        state: CohortState,
        sources: Sequence[Process | DecisionSource],
        metadata: EventLogMetadata,
        *,
        on_event: EventHook | None = None,
        on_year: YearHook | None = None,
    ) -> None:
        """Validate the sources and prepare the log builder."""
        validate_sources(sources)
        self.state = state
        self.sources = tuple(sources)
        self.metadata = metadata
        self.on_event = on_event
        self.on_year = on_year
        self._builder = EventLogBuilder(metadata)
        self._owners = {source.process_id: source for source in self.sources}

    def run(self, years: int) -> ExecutionResult:
        """Run the sources for a number of years.

        Parameters
        ----------
        years : int
            The horizon in years.

        Returns
        -------
        ExecutionResult
            The final state, log, and events.

        Raises
        ------
        ProcessError
            If a source emits an invalid or foreign event, or never stops emitting.
        """
        if isinstance(years, bool) or not isinstance(years, int) or years < 0:
            raise ProcessError("years must be a non-negative integer")
        history: list[Event] = []
        for year in range(years):
            year_events: list[Event] = []
            for phase in EVENT_PHASES:
                phase_sources = [source for source in self.sources if phase in source.phases]
                if not phase_sources:
                    continue
                for _batch in range(MAX_BATCHES_PER_PHASE):
                    batch: list[tuple[Event, Process | DecisionSource]] = []
                    for source in phase_sources:
                        context = ProcessContext(
                            year=year,
                            phase=phase,
                            scenario_id=self.metadata.scenario_id,
                            history=tuple(history),
                            year_events=tuple(year_events),
                        )
                        emitted = source.events(self.state, context)
                        for event in emitted:
                            self._validate_event(event, source, year, phase)
                            batch.append((event, source))
                    if not batch:
                        break
                    for event, source in sorted(batch, key=lambda item: item[0].sort_key):
                        before = self.state
                        self.state = source.apply(self.state, event)
                        if self.on_event is not None:
                            self.on_event(event, before, self.state)
                        year_events.append(event)
                else:
                    raise ProcessError(f"process {phase!r} exceeded the batch limit")
            ordered = tuple(sorted(year_events, key=lambda event: event.sort_key))
            self._builder.extend(ordered)
            history.extend(ordered)
            if self.on_year is not None:
                self.on_year(year, self.state, ordered)
        log = self._builder.build()
        return ExecutionResult(state=self.state, log=log, events=log.events)

    def _validate_event(
        self,
        event: Event,
        source: Process | DecisionSource,
        year: int,
        phase: str,
    ) -> None:
        """Validate one event against its source, year, phase, and scenario."""
        if not isinstance(event, Event):
            raise ProcessError("process events must be Event records")
        if event.process_id != source.process_id:
            raise ProcessError(
                f"process {source.process_id!r} emitted event {event.event_id!r} "
                f"for {event.process_id!r}"
            )
        if event.process_id not in self._owners:
            raise ProcessError(f"event {event.event_id!r} has no owning process")
        if event.year != year:
            raise ProcessError(f"event {event.event_id!r} has year {event.year}, expected {year}")
        if event.phase != phase:
            raise ProcessError(
                f"event {event.event_id!r} has phase {event.phase!r}, expected {phase!r}"
            )
        if event.scenario_id != self.metadata.scenario_id:
            raise ProcessError(
                f"event {event.event_id!r} names scenario {event.scenario_id!r}, "
                f"expected {self.metadata.scenario_id!r}"
            )
