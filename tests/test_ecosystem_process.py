"""Tests for the generic process contracts."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from ws4.ecosystem.events import Event
from ws4.ecosystem.process import (
    ProcessContext,
    ProcessError,
    validate_process,
    validate_sources,
)
from ws4.ecosystem.state import CohortState


@dataclass
class MarkerSource:
    """A minimal process that emits one marker event per year."""

    process_id: str
    process_phase: str = "effect"
    emitted: list[str] = field(default_factory=list)

    phases: tuple[str, ...] = ("effect",)
    state_reads: frozenset[str] = frozenset()
    state_writes: frozenset[str] = frozenset({"fuel_t_ha"})

    def events(self, state: CohortState, context: ProcessContext) -> tuple[Event, ...]:
        """Return one event per year after the first call."""
        event_id = f"{self.process_id}-{context.year}"
        if any(event.event_id == event_id for event in context.year_events):
            return ()
        return (
            Event(
                event_id=event_id,
                process_id=self.process_id,
                event_type="marker",
                time=float(context.year),
                year=context.year,
                phase=self.process_phase,
                source="test",
                scenario_id=context.scenario_id,
                fragment_ids=(0,),
            ),
        )

    def apply(self, state: CohortState, event: Event) -> CohortState:
        """Record the event and return the state unchanged."""
        self.emitted.append(event.event_id)
        return state


def test_context_validates_year_phase_and_scenario() -> None:
    context = ProcessContext(0, "effect", "scenario")
    assert context.scenario_id == "scenario"
    with pytest.raises(ProcessError, match="non-negative"):
        ProcessContext(-1, "effect", "scenario")
    with pytest.raises(ProcessError, match="phase"):
        ProcessContext(0, "unknown", "scenario")
    with pytest.raises(ProcessError, match="scenario_id"):
        ProcessContext(0, "effect", "")


def test_valid_process_declaration_passes() -> None:
    source = MarkerSource("marker")
    validate_process(source)
    validate_sources((source,))


def test_invalid_process_declarations_fail() -> None:
    source = MarkerSource("marker")
    source.phases = ()
    with pytest.raises(ProcessError, match="at least one phase"):
        validate_process(source)

    source = MarkerSource("marker")
    source.phases = ("effect", "unknown")
    with pytest.raises(ProcessError, match="unknown phase"):
        validate_process(source)

    source = MarkerSource("marker")
    object.__setattr__(source, "state_writes", {"fuel_t_ha"})
    with pytest.raises(ProcessError, match="state_writes"):
        validate_process(source)

    with pytest.raises(ProcessError, match="duplicate process id"):
        validate_sources((MarkerSource("same"), MarkerSource("same")))
    with pytest.raises(ProcessError, match="at least one"):
        validate_sources(())
