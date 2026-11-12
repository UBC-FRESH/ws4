"""The process protocol for the stochastic landscape engine.

The P144 fire slice ran fire and salvage through a dedicated ``FireRun`` loop. This module
defines the general contract the executor uses instead: a source declares the annual phases it
participates in, the state variables it reads and writes, and the events and state transition
for its own events. The executor does not know what fire, salvage, succession, or a synthetic
test process mean.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .events import EVENT_PHASES, Event
from .state import CohortState


class ProcessError(RuntimeError):
    """Raised when a process declaration or emitted event is invalid."""


@dataclass(frozen=True)
class ProcessContext:
    """The state visible to one process when it emits events.

    Parameters
    ----------
    year : int
        The annual accounting year.
    phase : str
        The current phase from :data:`ws4.ecosystem.events.EVENT_PHASES`.
    scenario_id : str
        The scenario that owns the run.
    history : tuple of Event
        All events emitted before the current year.
    year_events : tuple of Event
        Events emitted in the current year before this call.
    """

    year: int
    phase: str
    scenario_id: str
    history: tuple[Event, ...] = ()
    year_events: tuple[Event, ...] = ()

    def __post_init__(self) -> None:
        """Validate the context."""
        if isinstance(self.year, bool) or not isinstance(self.year, int) or self.year < 0:
            raise ProcessError("year must be a non-negative integer")
        if self.phase not in EVENT_PHASES:
            raise ProcessError(f"phase must be one of: {', '.join(EVENT_PHASES)}")
        if not isinstance(self.scenario_id, str) or not self.scenario_id.strip():
            raise ProcessError("scenario_id must be a non-empty string")
        object.__setattr__(self, "scenario_id", self.scenario_id.strip())
        object.__setattr__(self, "history", tuple(self.history))
        object.__setattr__(self, "year_events", tuple(self.year_events))


@runtime_checkable
class Process(Protocol):
    """An uncontrolled event source.

    A process owns its own events. The executor calls ``events`` until a source emits no more
    events for the phase, applying each batch in event-key order before asking again.
    """

    process_id: str
    phases: tuple[str, ...]
    state_reads: frozenset[str]
    state_writes: frozenset[str]

    def events(self, state: CohortState, context: ProcessContext) -> Sequence[Event]:
        """Return the next batch of events for the context phase.

        Parameters
        ----------
        state : CohortState
            The current cohort state.
        context : ProcessContext
            The year, phase, history, and current-year events.

        Returns
        -------
        sequence of Event
            The next batch, or an empty sequence when the source is finished.
        """
        ...

    def apply(self, state: CohortState, event: Event) -> CohortState:
        """Apply one event produced by this process.

        Parameters
        ----------
        state : CohortState
            The state before the event.
        event : Event
            An event owned by this process.

        Returns
        -------
        CohortState
            The state after the event.
        """
        ...


@runtime_checkable
class DecisionSource(Protocol):
    """A controlled event source.

    A static schedule is a degenerate decision source. The executor treats decision and
    process events the same way; the distinction is for provenance and future policy search.
    """

    process_id: str
    phases: tuple[str, ...]
    state_reads: frozenset[str]
    state_writes: frozenset[str]

    def events(self, state: CohortState, context: ProcessContext) -> Sequence[Event]:
        """Return the next batch of controlled events for the context phase.

        Parameters
        ----------
        state : CohortState
            The current cohort state.
        context : ProcessContext
            The year, phase, history, and current-year events.

        Returns
        -------
        sequence of Event
            The next batch, or an empty sequence when the source is finished.
        """
        ...

    def apply(self, state: CohortState, event: Event) -> CohortState:
        """Apply one controlled event.

        Parameters
        ----------
        state : CohortState
            The state before the event.
        event : Event
            An event owned by this decision source.

        Returns
        -------
        CohortState
            The state after the event.
        """
        ...


def validate_process(source: Process | DecisionSource) -> None:
    """Validate one process declaration.

    Parameters
    ----------
    source : Process or DecisionSource
        The source to validate.

    Raises
    ------
    ProcessError
        If the id, phases, or state declarations are invalid.
    """
    process_id = getattr(source, "process_id", None)
    if not isinstance(process_id, str) or not process_id.strip():
        raise ProcessError("process_id must be a non-empty string")
    phases = getattr(source, "phases", None)
    if not isinstance(phases, tuple) or not phases:
        raise ProcessError(f"process {process_id!r} must declare at least one phase")
    for phase in phases:
        if phase not in EVENT_PHASES:
            raise ProcessError(f"process {process_id!r} declares an unknown phase: {phase!r}")
    if len(set(phases)) != len(phases):
        raise ProcessError(f"process {process_id!r} declares a duplicate phase")
    for field in ("state_reads", "state_writes"):
        value = getattr(source, field, None)
        if not isinstance(value, frozenset):
            raise ProcessError(f"process {process_id!r} {field} must be a frozenset")
        for name in value:
            if not isinstance(name, str) or not name.strip():
                raise ProcessError(f"process {process_id!r} has an invalid state variable name")
    if not callable(getattr(source, "events", None)):
        raise ProcessError(f"process {process_id!r} has no events method")
    if not callable(getattr(source, "apply", None)):
        raise ProcessError(f"process {process_id!r} has no apply method")


def validate_sources(sources: Sequence[Process | DecisionSource]) -> None:
    """Validate a source set and require unique process ids.

    Parameters
    ----------
    sources : sequence of Process or DecisionSource
        The sources the executor will run.

    Raises
    ------
    ProcessError
        If the set is empty, has duplicate ids, or contains an invalid source.
    """
    if not sources:
        raise ProcessError("at least one process source is required")
    seen: set[str] = set()
    for source in sources:
        validate_process(source)
        if source.process_id in seen:
            raise ProcessError(f"duplicate process id: {source.process_id!r}")
        seen.add(source.process_id)
