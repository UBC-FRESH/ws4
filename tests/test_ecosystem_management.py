"""Tests for the schedule-to-cohort management bridge."""

from __future__ import annotations

from pathlib import Path

import pytest
from ws4.ecosystem.ensemble import (
    ProcessEnsembleConfig,
    ProcessScenarioResult,
    run_process_scenario,
)
from ws4.ecosystem.events import Event
from ws4.ecosystem.fire import FireConfig, synthetic_grid
from ws4.ecosystem.management import (
    ManagementError,
    ScheduleSource,
    load_block_fragments,
    load_schedule,
)
from ws4.ecosystem.process import ProcessContext


def _config(management: ScheduleSource | None = None) -> ProcessEnsembleConfig:
    """Return a fire-free process configuration for state tests."""
    return ProcessEnsembleConfig(
        horizon_years=1,
        fire=FireConfig(ignition_rate_per_fragment_year=0.0),
        management=management,
    )


def test_load_schedule_and_fragment_mapping(tmp_path: Path) -> None:
    schedule_path = tmp_path / "schedule.csv"
    schedule_path.write_text("block_id,treatment,offset\n1,CC,0\n2,CT,1\n", encoding="utf-8")
    mapping_path = tmp_path / "map.csv"
    mapping_path.write_text("block_id,fragment_id\n1,1\n1,2\n2,3\n", encoding="utf-8")

    assert load_schedule(schedule_path) == {1: (("CC", 0),), 2: (("CT", 1),)}
    assert load_block_fragments(mapping_path) == {1: (1, 2), 2: (3,)}


def test_harvest_reduces_biomass_and_conserves_area() -> None:
    _schema, state, edges = synthetic_grid(3, 3)
    source = ScheduleSource({1: (("CC", 0),)}, {1: (1, 2)}, harvest_fraction=1.0)
    result = run_process_scenario(state, edges, _config(source), scenario_id="m", seed=1)

    assert any(event.event_type == "harvest" for event in result.log.events)
    result.state.check_area_conservation()
    harvested = result.state.cohorts[result.state.cohorts["fragment_id"].isin([1, 2])]
    assert (harvested["biomass_t_ha"] == 0.0).all()


def test_harvest_event_timing_and_retention() -> None:
    _schema, state, _edges = synthetic_grid(3, 3)
    source = ScheduleSource({1: (("CC", 0),)}, {1: (1,)}, harvest_fraction=0.5)
    context = ProcessContext(0, "treatment", "m")
    events = source.events(state, context)

    assert len(events) == 1
    updated = source.apply(state, events[0])
    updated.check_area_conservation()
    group = updated.cohorts[updated.cohorts["fragment_id"] == 1]
    assert float(group["area_fraction"].sum()) == pytest.approx(1.0)
    before = state.cohorts[state.cohorts["fragment_id"] == 1]
    assert float((group["biomass_t_ha"] * group["area_fraction"]).sum()) < float(
        (before["biomass_t_ha"] * before["area_fraction"]).sum()
    )


def test_schedule_rejects_unknown_mapping_and_duplicate_rows(tmp_path: Path) -> None:
    with pytest.raises(ManagementError, match="no fragment mapping"):
        ScheduleSource({1: (("CC", 0),)}, {2: (1,)})

    path = tmp_path / "bad.csv"
    path.write_text("block_id,treatment,offset\n1,CC,0\n1,CC,0\n", encoding="utf-8")
    with pytest.raises(ManagementError, match="duplicate"):
        load_schedule(path)


def test_harvest_event_type_is_ignored_by_other_processes() -> None:
    _schema, state, _edges = synthetic_grid(2, 2)
    source = ScheduleSource({1: (("CC", 0),)}, {1: (1,)})
    event = Event(
        event_id="other",
        process_id="management",
        event_type="other",
        time=0.5,
        year=0,
        phase="treatment",
        source="test",
        fragment_ids=(1,),
    )

    assert source.apply(state, event) is state


def test_harvest_schedule_changes_process_metrics() -> None:
    from ws4.ecosystem.ensemble import run_process_scenario

    _schema, state, edges = synthetic_grid(3, 3)
    base = ProcessEnsembleConfig(
        horizon_years=2,
        fire=FireConfig(ignition_rate_per_fragment_year=0.5),
    )
    source = ScheduleSource(
        {1: (("CC", 0),)},
        {1: tuple(range(1, 10))},
        harvest_fraction=1.0,
    )
    harvested = ProcessEnsembleConfig(
        horizon_years=2,
        fire=FireConfig(ignition_rate_per_fragment_year=0.5),
        management=source,
    )

    baseline = run_process_scenario(state, edges, base, scenario_id="base", seed=3)
    cleared = run_process_scenario(state, edges, harvested, scenario_id="cleared", seed=3)

    def final_metric(result: ProcessScenarioResult, account: str) -> float:
        frame = result.values[result.values["account"] == account]
        return float(frame.iloc[-1]["value"])

    assert final_metric(cleared, "state.biomass_t") < final_metric(baseline, "state.biomass_t")
    assert final_metric(cleared, "state.fuel_t") < final_metric(baseline, "state.fuel_t")
