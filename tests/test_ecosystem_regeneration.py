"""Tests for stochastic juvenile establishment."""

from __future__ import annotations

from ws4.ecosystem.executor import Executor
from ws4.ecosystem.fire import synthetic_grid
from ws4.ecosystem.log import EventLogMetadata
from ws4.ecosystem.regeneration import RegenerationConfig, RegenerationProcess
from ws4.ecosystem.state import CohortState
from ws4.ecosystem.tape import RandomTape


def _juvenile_state() -> CohortState:
    """Return a state whose cohorts are juvenile and empty."""
    _schema, state, _edges = synthetic_grid(3, 3)
    frame = state.cohorts.copy()
    frame["age"] = 0
    frame["biomass_t_ha"] = 0.0
    frame["fuel_t_ha"] = 0.0
    return CohortState(
        cohorts=frame.reset_index(drop=True),
        schema=state.schema,
        fragment_areas=state.fragment_areas,
    )


def _metadata() -> EventLogMetadata:
    """Return fixed metadata."""
    return EventLogMetadata(scenario_id="regen-test", scenario_seed=13)


def _process(probability: float) -> RegenerationProcess:
    """Return a regeneration process with a fixed seed."""
    return RegenerationProcess(
        RegenerationConfig(establishment_probability=probability),
        RandomTape(13),
        scenario_id="regen-test",
    )


def test_regeneration_establishes_biomass_and_fuel() -> None:
    state = _juvenile_state()
    result = Executor(state, (_process(1.0),), _metadata()).run(1)

    assert (result.state.cohorts["biomass_t_ha"] >= 20.0).all()
    assert (result.state.cohorts["fuel_t_ha"] >= 3.0).all()
    result.state.check_area_conservation()
    assert any(event.event_type == "regeneration" for event in result.log.events)


def test_regeneration_probability_zero_does_nothing() -> None:
    state = _juvenile_state()
    result = Executor(state, (_process(0.0),), _metadata()).run(1)

    assert (result.state.cohorts["biomass_t_ha"] == 0.0).all()
    assert not any(event.event_type == "regeneration" for event in result.log.events)


def test_regeneration_replay_is_exact() -> None:
    first = Executor(_juvenile_state(), (_process(0.5),), _metadata()).run(3)
    second = Executor(_juvenile_state(), (_process(0.5),), _metadata()).run(3)

    assert first.log.replay_token == second.log.replay_token
    assert first.state.cohorts.equals(second.state.cohorts)


def test_regeneration_skips_old_cohorts() -> None:
    _schema, state, _edges = synthetic_grid(3, 3)
    frame = state.cohorts.copy()
    frame["age"] = 20
    frame["biomass_t_ha"] = 100.0
    mature = CohortState(
        cohorts=frame.reset_index(drop=True),
        schema=state.schema,
        fragment_areas=state.fragment_areas,
    )

    result = Executor(mature, (_process(1.0),), _metadata()).run(1)

    assert result.state.cohorts.equals(mature.cohorts)
    assert not any(event.event_type == "regeneration" for event in result.log.events)
