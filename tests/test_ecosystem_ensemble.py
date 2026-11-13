"""Tests for process-driven scenario ensembles."""

from __future__ import annotations

from pathlib import Path

import pytest
from ws4.ecosystem.ensemble import (
    ProcessEnsembleConfig,
    ProcessEnsembleError,
    run_process_ensemble,
    run_process_scenario,
)
from ws4.ecosystem.fire import FireConfig, synthetic_grid
from ws4.ecosystem.regeneration import RegenerationConfig
from ws4.ecosystem.scenarios import Scenario, ScenarioSet
from ws4.ecosystem.succession import SpeciesGrowth, SuccessionConfig
from ws4.opt.objective import Target


def _config() -> ProcessEnsembleConfig:
    """Return a small process configuration."""
    return ProcessEnsembleConfig(
        horizon_years=2,
        fire=FireConfig(
            ignition_rate_per_fragment_year=1.0,
            base_spread_probability=1.0,
            salvage_delay_years=0,
        ),
        regeneration=RegenerationConfig(establishment_probability=1.0),
    )


def test_one_scenario_writes_process_metrics() -> None:
    _schema, state, edges = synthetic_grid(4, 4)
    result = run_process_scenario(state, edges, _config(), scenario_id="one", seed=5)

    assert set(result.values["account"]) >= {
        "fire.count",
        "fire.burned_area_ha",
        "state.biomass_t",
        "bridge.volume_m3",
    }
    assert result.log.replay_token
    assert result.values["offset"].nunique() == 2


def test_ensemble_risk_aggregation_and_write(tmp_path: Path) -> None:
    _schema, state, edges = synthetic_grid(4, 4)
    scenarios = ScenarioSet(
        (Scenario("low", 5, weight=1.0), Scenario("high", 6, weight=3.0)),
        name="process-test",
    )
    targets = (Target(account="fire.burned_area_ha", period=1, minimum=0.0, aggregation="mean"),)

    result = run_process_ensemble(state, edges, _config(), scenarios, targets)
    result.write(tmp_path / "ensemble")

    assert set(result.values["scenario"]) == {"low", "high"}
    assert not result.aggregated.empty
    assert result.aggregated["account"].iloc[0].startswith("risk.mean")
    assert (tmp_path / "ensemble" / "process_values.csv").is_file()
    assert (tmp_path / "ensemble" / "process_aggregated.csv").is_file()
    assert (tmp_path / "ensemble" / "process_summary.json").is_file()


def test_scenario_replay_is_exact() -> None:
    _schema, state, edges = synthetic_grid(4, 4)
    first = run_process_scenario(state, edges, _config(), scenario_id="one", seed=9)
    second = run_process_scenario(state, edges, _config(), scenario_id="one", seed=9)

    assert first.log.replay_token == second.log.replay_token
    assert first.values.equals(second.values)


def test_common_random_numbers_share_fire_draws() -> None:
    _schema, state, edges = synthetic_grid(4, 4)
    first = run_process_scenario(
        state,
        edges,
        _config(),
        scenario_id="one",
        seed=11,
    )
    second = run_process_scenario(
        state,
        edges,
        ProcessEnsembleConfig(
            horizon_years=2,
            fire=FireConfig(
                ignition_rate_per_fragment_year=1.0,
                base_spread_probability=1.0,
                salvage_delay_years=0,
            ),
            succession=SuccessionConfig(
                species={"PL": SpeciesGrowth(max_biomass_t_ha=120.0, growth_rate=0.2)}
            ),
            regeneration=RegenerationConfig(establishment_probability=1.0),
        ),
        scenario_id="two",
        seed=11,
    )

    first_ignitions = [
        event.event_id for event in first.log.events if event.event_type == "fire_ignition"
    ]
    second_ignitions = [
        event.event_id for event in second.log.events if event.event_type == "fire_ignition"
    ]
    assert first_ignitions
    assert first_ignitions == second_ignitions


def test_ensemble_rejects_bad_horizon() -> None:
    with pytest.raises(ProcessEnsembleError, match="horizon_years"):
        ProcessEnsembleConfig(horizon_years=-1, fire=FireConfig())
