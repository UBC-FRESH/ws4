"""Tests for process-conditioned schedule evaluation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ws4.ecosystem.evaluation import (
    PROCESS_EVALUATION_VERSION,
    ProcessEvaluationError,
    evaluate_process_schedule,
)
from ws4.ecosystem.fire import FireConfig, synthetic_grid
from ws4.ecosystem.landis import LandisSuccessionProcess, landis_reference_config
from ws4.ecosystem.management import ManagementError


def _fire() -> FireConfig:
    """Return a fire-free configuration for deterministic evaluation tests."""
    return FireConfig(ignition_rate_per_fragment_year=0.0)


def _number(value: object) -> float:
    """Return a numeric table value."""
    assert isinstance(value, (int, float))
    assert not isinstance(value, bool)
    return float(value)


def _accounts(evaluation: object) -> dict[str, float]:
    """Return an evaluation's account mapping."""
    from ws4.ecosystem.evaluation import ProcessScheduleEvaluation

    assert isinstance(evaluation, ProcessScheduleEvaluation)
    return {
        str(row.account): _number(row.value) for row in evaluation.accounts.itertuples(index=False)
    }


def test_schedule_evaluation_harvests_and_conserves_area() -> None:
    _schema, state, edges = synthetic_grid(3, 3)
    evaluation = evaluate_process_schedule(
        state,
        edges,
        {1: (("CC", 0),)},
        {1: (1, 2)},
        horizon_years=1,
        fire=_fire(),
        seed=7,
    )

    accounts = _accounts(evaluation)
    assert accounts["harvest.count_total"] == 2.0
    assert accounts["harvest.area_ha_total"] == 20.0
    assert accounts["state.biomass_t"] < 9000.0
    counts = evaluation.summary()["event_counts"]
    assert isinstance(counts, dict)
    assert counts["harvest"] == 2
    evaluation.state.check_area_conservation()
    assert evaluation.values["offset"].nunique() == 1


def test_harvest_reduces_biomass_against_the_baseline() -> None:
    _schema, state, edges = synthetic_grid(3, 3)
    baseline = evaluate_process_schedule(
        state,
        edges,
        {},
        {},
        horizon_years=1,
        fire=_fire(),
        seed=7,
    )
    harvested = evaluate_process_schedule(
        state,
        edges,
        {1: (("CC", 0),)},
        {1: (1, 2)},
        horizon_years=1,
        fire=_fire(),
        seed=7,
    )

    assert _accounts(baseline)["harvest.count_total"] == 0.0
    assert _accounts(harvested)["state.biomass_t"] < _accounts(baseline)["state.biomass_t"]


def test_evaluation_is_deterministic() -> None:
    _schema, state, edges = synthetic_grid(3, 3)
    source = LandisSuccessionProcess(landis_reference_config(["pinustro"]))
    first = evaluate_process_schedule(
        state,
        edges,
        {1: (("CC", 0),)},
        {1: (1, 2)},
        horizon_years=2,
        fire=_fire(),
        succession_process=source,
        scenario_id="landis",
        seed=11,
    )
    second = evaluate_process_schedule(
        state,
        edges,
        {1: (("CC", 0),)},
        {1: (1, 2)},
        horizon_years=2,
        fire=_fire(),
        succession_process=source,
        scenario_id="landis",
        seed=11,
    )

    assert first.summary() == second.summary()
    assert first.log.replay_token == second.log.replay_token
    assert first.values.equals(second.values)
    counts = first.summary()["event_counts"]
    assert isinstance(counts, dict)
    assert counts["landis_succession"] == 18


def test_evaluation_artifact_writes_json_and_csv(tmp_path: Path) -> None:
    from ws4.opt.objective import Target

    _schema, state, edges = synthetic_grid(2, 2)
    evaluation = evaluate_process_schedule(
        state,
        edges,
        {1: (("CC", 0),)},
        {1: (1,)},
        horizon_years=1,
        fire=_fire(),
        targets=(Target(account="harvest.area_ha_total", period=1, minimum=1.0),),
    )
    evaluation.write(tmp_path / "evaluation")

    summary = json.loads((tmp_path / "evaluation" / "process_evaluation.json").read_text())
    assert summary["schema_version"] == PROCESS_EVALUATION_VERSION
    assert summary["scenario_id"] == "process-schedule"
    accounts = summary["accounts"]
    assert isinstance(accounts, dict)
    assert accounts["harvest.count_total"] == 1.0
    assert summary["objective"] == 0.0
    assert summary["target_accounts"] == ["harvest.area_ha_total"]
    assert (tmp_path / "evaluation" / "process_evaluation_values.csv").is_file()
    assert (tmp_path / "evaluation" / "process_evaluation_accounts.csv").is_file()


def test_zero_horizon_is_well_defined() -> None:
    _schema, state, edges = synthetic_grid(2, 2)
    evaluation = evaluate_process_schedule(
        state,
        edges,
        {1: (("CC", 0),)},
        {1: (1,)},
        horizon_years=0,
        fire=_fire(),
    )

    assert evaluation.summary()["final_offset"] == 0
    assert _accounts(evaluation)["harvest.count_total"] == 0.0
    assert evaluation.values.empty


def test_invalid_inputs_fail_loudly() -> None:
    _schema, state, edges = synthetic_grid(2, 2)
    with pytest.raises(ProcessEvaluationError, match="horizon_years"):
        evaluate_process_schedule(state, edges, {}, {}, horizon_years=-1, fire=_fire())
    with pytest.raises(ProcessEvaluationError, match="seed"):
        evaluate_process_schedule(state, edges, {}, {}, horizon_years=1, fire=_fire(), seed=-1)
    with pytest.raises(ProcessEvaluationError, match="scenario_id"):
        evaluate_process_schedule(
            state, edges, {}, {}, horizon_years=1, fire=_fire(), scenario_id=""
        )
    with pytest.raises(ManagementError, match="no fragment mapping"):
        evaluate_process_schedule(
            state, edges, {1: (("CC", 0),)}, {}, horizon_years=1, fire=_fire()
        )
    with pytest.raises(ManagementError, match="no fragment mapping"):
        evaluate_process_schedule(
            state, edges, {1: (("CC", 0),)}, {2: (1,)}, horizon_years=1, fire=_fire()
        )


def test_objective_adapter_prices_final_accounts() -> None:
    from ws4.opt.objective import Target

    _schema, state, edges = synthetic_grid(3, 3)
    evaluation = evaluate_process_schedule(
        state,
        edges,
        {1: (("CC", 0),)},
        {1: (1, 2)},
        horizon_years=1,
        fire=_fire(),
        targets=(Target(account="harvest.area_ha_total", period=1, minimum=30.0),),
    )

    assert evaluation.objective == 10.0
    assert evaluation.terms == (10.0,)
    summary = evaluation.summary()
    assert summary["objective"] == 10.0
    assert summary["target_terms"] == [10.0]
    assert summary["target_accounts"] == ["harvest.area_ha_total"]


def test_satisfied_objective_target_has_zero_penalty() -> None:
    from ws4.opt.objective import Target

    _schema, state, edges = synthetic_grid(3, 3)
    evaluation = evaluate_process_schedule(
        state,
        edges,
        {1: (("CC", 0),)},
        {1: (1, 2)},
        horizon_years=1,
        fire=_fire(),
        targets=(Target(account="harvest.area_ha_total", period=1, minimum=20.0),),
    )

    assert evaluation.objective == 0.0
    assert evaluation.terms == (0.0,)


def test_unsupported_targets_fail_loudly() -> None:
    from ws4.opt.objective import Target

    _schema, state, edges = synthetic_grid(2, 2)
    cases = (
        Target(account="harvest.area_ha_total", period=2),
        Target(account="harvest.area_ha_total", period=1, flow="even"),
        Target(account="product.volume", period=1),
        Target(account="harvest.area_ha_total", period=1, aggregation="mean"),
        Target(account="harvest.area_ha_total", period=0),
        Target(account="not.an.account", period=1),
    )
    for target in cases:
        with pytest.raises(ProcessEvaluationError):
            evaluate_process_schedule(
                state,
                edges,
                {1: (("CC", 0),)},
                {1: (1,)},
                horizon_years=1,
                fire=_fire(),
                targets=(target,),
            )
