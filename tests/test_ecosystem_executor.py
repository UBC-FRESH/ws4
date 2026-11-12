"""Tests for the generic multi-process executor."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from ws4.ecosystem.events import Event
from ws4.ecosystem.executor import Executor
from ws4.ecosystem.fire import (
    FireConfig,
    FireProcess,
    FireProcessSource,
    SalvageProcessSource,
    SalvageSource,
    synthetic_grid,
)
from ws4.ecosystem.log import EventLogMetadata
from ws4.ecosystem.process import ProcessContext, ProcessError
from ws4.ecosystem.state import CohortState
from ws4.ecosystem.tape import RandomTape


@dataclass
class MutatingSource:
    """Emit one marker event per year and reduce the fragment fuel."""

    process_id: str
    scale: float = 0.9
    order: list[str] = field(default_factory=list)

    phases: tuple[str, ...] = ("effect",)
    state_reads: frozenset[str] = frozenset({"fuel_t_ha"})
    state_writes: frozenset[str] = frozenset({"fuel_t_ha"})

    def events(self, state: CohortState, context: ProcessContext) -> tuple[Event, ...]:
        """Return one event per year."""
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
                phase="effect",
                source="test",
                scenario_id=context.scenario_id,
                fragment_ids=(1,),
            ),
        )

    def apply(self, state: CohortState, event: Event) -> CohortState:
        """Record the event and reduce fragment 0 fuel."""
        self.order.append(event.event_id)
        frame = state.cohorts.copy()
        frame.loc[frame["fragment_id"] == 1, "fuel_t_ha"] *= self.scale
        return CohortState(
            cohorts=frame.reset_index(drop=True),
            schema=state.schema,
            fragment_areas=state.fragment_areas,
        )


@dataclass
class ForeignSource(MutatingSource):
    """Emit an event owned by another process."""

    def events(self, state: CohortState, context: ProcessContext) -> tuple[Event, ...]:
        """Return an event with a foreign process id."""
        return (
            Event(
                event_id=f"{self.process_id}-{context.year}",
                process_id="foreign",
                event_type="marker",
                time=float(context.year),
                year=context.year,
                phase="effect",
                source="test",
                scenario_id=context.scenario_id,
                fragment_ids=(1,),
            ),
        )


def _state() -> CohortState:
    """Return a small synthetic cohort state."""
    _schema, state, _edges = synthetic_grid(3, 3)
    return state


def _metadata() -> EventLogMetadata:
    """Return fixed log metadata."""
    return EventLogMetadata(scenario_id="executor-test", scenario_seed=7)


def test_executor_runs_two_sources_in_event_order() -> None:
    first = MutatingSource("a")
    second = MutatingSource("b")
    applied: list[str] = []
    years: list[tuple[int, tuple[str, ...]]] = []
    state = _state()
    before_fuel = float(state.cohorts["fuel_t_ha"].sum())
    executor = Executor(
        state,
        (first, second),
        _metadata(),
        on_event=lambda event, _before, _after: applied.append(event.event_id),
        on_year=lambda year, _state, events: years.append(
            (year, tuple(event.event_id for event in events))
        ),
    )

    result = executor.run(2)

    assert applied == ["a-0", "b-0", "a-1", "b-1"]
    assert [event.event_id for event in result.log.events] == applied
    assert years[0] == (0, ("a-0", "b-0"))
    assert years[1] == (1, ("a-1", "b-1"))
    assert float(result.state.cohorts["fuel_t_ha"].sum()) < before_fuel
    assert result.log.replay_token


def test_executor_replay_is_exact() -> None:
    first = Executor(_state(), (MutatingSource("a"),), _metadata()).run(3)
    second = Executor(_state(), (MutatingSource("a"),), _metadata()).run(3)

    assert first.log.replay_token == second.log.replay_token
    assert [event.event_id for event in first.log.events] == [
        event.event_id for event in second.log.events
    ]


def test_executor_rejects_a_foreign_event() -> None:
    executor = Executor(_state(), (ForeignSource("a"),), _metadata())

    with pytest.raises(ProcessError, match="emitted event"):
        executor.run(1)


def test_fire_and_a_synthetic_process_share_one_run() -> None:
    _schema, state, edges = synthetic_grid(5, 5)
    tape = RandomTape(3)
    fire = FireProcess(
        FireConfig(ignition_rate_per_fragment_year=1.0, base_spread_probability=1.0),
        edges,
        tape,
        scenario_id="executor-test",
    )
    salvage = SalvageSource(
        FireConfig(ignition_rate_per_fragment_year=1.0), scenario_id="executor-test"
    )
    marker = MutatingSource("marker", scale=0.95)
    sources = (
        FireProcessSource(fire),
        marker,
        SalvageProcessSource(salvage),
    )
    executor = Executor(state, sources, _metadata())

    result = executor.run(2)

    event_types = {event.event_type for event in result.log.events}
    assert "fire" in event_types
    assert "marker" in event_types
    assert any(event.process_id == "marker" for event in result.log.events)
    assert any(event.process_id == "salvage" for event in result.log.events)
    assert float(result.state.cohorts["fuel_t_ha"].sum()) < 500.0
