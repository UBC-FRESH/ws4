"""Tests for the deterministic succession process."""

from __future__ import annotations

import math

import pytest
from ws4.ecosystem.executor import Executor
from ws4.ecosystem.fire import synthetic_grid
from ws4.ecosystem.log import EventLogMetadata
from ws4.ecosystem.state import CohortState
from ws4.ecosystem.succession import SpeciesGrowth, SuccessionConfig, SuccessionProcess


def _state() -> CohortState:
    """Return a small synthetic cohort state."""
    _schema, state, _edges = synthetic_grid(3, 3)
    return state


def _metadata() -> EventLogMetadata:
    """Return fixed event-log metadata."""
    return EventLogMetadata(scenario_id="succession-test", scenario_seed=11)


def test_succession_ages_and_grows_cohorts() -> None:
    state = _state()
    before_age = float(state.cohorts["age"].mean())
    before_biomass = float(state.cohorts["biomass_t_ha"].sum())
    executor = Executor(state, (SuccessionProcess(),), _metadata())

    result = executor.run(2)

    assert float(result.state.cohorts["age"].mean()) == pytest.approx(before_age + 2.0)
    assert float(result.state.cohorts["biomass_t_ha"].sum()) > before_biomass
    result.state.check_area_conservation()


def test_succession_respects_the_biomass_cap() -> None:
    state = _state()
    config = SuccessionConfig(
        species={"PL": SpeciesGrowth(max_biomass_t_ha=101.0, growth_rate=0.5)}
    )
    executor = Executor(state, (SuccessionProcess(config),), _metadata())

    result = executor.run(5)

    assert float(result.state.cohorts["biomass_t_ha"].max()) <= 101.0 + 1e-9
    assert all(math.isfinite(value) for value in result.state.cohorts["biomass_t_ha"])


def test_succession_replay_is_exact() -> None:
    first = Executor(_state(), (SuccessionProcess(),), _metadata()).run(3)
    second = Executor(_state(), (SuccessionProcess(),), _metadata()).run(3)

    assert first.log.replay_token == second.log.replay_token
    assert first.state.cohorts.equals(second.state.cohorts)


def test_unknown_species_uses_the_default() -> None:
    state = _state()
    config = SuccessionConfig(default=SpeciesGrowth(max_biomass_t_ha=120.0, growth_rate=0.1))
    result = Executor(state, (SuccessionProcess(config),), _metadata()).run(1)

    assert float(result.state.cohorts["biomass_t_ha"].max()) <= 120.0
