"""Tests for fire-regime risk summaries over event records."""

from __future__ import annotations

import json
import math

import pytest
from ws4.ecosystem.events import Event
from ws4.ecosystem.log import EventLog, EventLogMetadata
from ws4.fire.regime import FireRegimeParameters
from ws4.fire.risk import (
    FIRE_RISK_VERSION,
    FireEventRecord,
    FireRiskError,
    events_from_log,
    summarize_event_log,
    summarize_event_logs,
    summarize_fire_events,
)


def _event(event_id: str, year: int, area: float | None, event_type: str = "fire") -> Event:
    """Return a minimal event for the summary tests."""
    return Event(
        event_id=event_id,
        process_id="fire" if event_type == "fire" else "test",
        event_type=event_type,
        time=float(year) + 0.5,
        year=year,
        phase="effect",
        source="test",
        scenario_id="toy",
        area_ha=area,
    )


def _log(events: tuple[Event, ...], scenario: str = "toy") -> EventLog:
    """Return an event log containing the events."""
    return EventLog(
        metadata=EventLogMetadata(scenario_id=scenario),
        events=tuple(
            Event(
                event_id=event.event_id,
                process_id=event.process_id,
                event_type=event.event_type,
                time=event.time,
                year=event.year,
                phase=event.phase,
                source=event.source,
                scenario_id=scenario,
                area_ha=event.area_ha,
            )
            for event in events
        ),
    )


def _target() -> FireRegimeParameters:
    """Return a target regime for the exact diagnostics test."""
    return FireRegimeParameters(
        n_fires=3,
        ignition_rate=0.002,
        p_escape=0.5,
        mean_escaped_size_ha=75.0,
        max_escaped_size_ha=100.0,
        empirical_burn_rate=0.02,
        p_ignition=0.0125,
        max_burn_cells=12,
    )


def test_summary_matches_the_synthetic_event_log() -> None:
    summary = summarize_fire_events(
        [
            FireEventRecord(0, 5.0),
            FireEventRecord(0, 20.0),
            FireEventRecord(2, 100.0),
            FireEventRecord(3, 1.0),
            FireEventRecord(3, 2.0),
        ],
        years=4,
        burnable_area_ha=1000.0,
        cell_size_ha=10.0,
    )

    assert summary.years == 4
    assert [record.burned_area_ha for record in summary.annual] == [25.0, 0.0, 100.0, 3.0]
    assert [record.fire_count for record in summary.annual] == [2, 0, 1, 2]
    assert [record.escaped_fire_count for record in summary.annual] == [1, 0, 1, 0]
    assert summary.total_burned_ha == pytest.approx(128.0)
    assert summary.mean_annual_burned_ha == pytest.approx(32.0)
    assert summary.median_annual_burned_ha == pytest.approx(14.0)
    assert summary.p90_annual_burned_ha == pytest.approx(77.5)
    assert summary.max_annual_burned_ha == pytest.approx(100.0)
    assert summary.burn_probability == pytest.approx(0.75)
    assert summary.annual_burn_rate == pytest.approx(0.032)
    assert summary.fire_return_interval_years == pytest.approx(31.25)
    assert summary.fire_count == 5
    assert summary.escaped_fire_count == 2
    assert summary.escaped_fires_per_year == pytest.approx(0.5)
    assert summary.mean_fire_size_ha == pytest.approx(25.6)
    assert summary.median_fire_size_ha == pytest.approx(5.0)
    assert summary.p90_fire_size_ha == pytest.approx(68.0)
    assert summary.max_fire_size_ha == pytest.approx(100.0)
    assert summary.diagnostics is None


def test_summary_reuses_the_target_regime_diagnostics() -> None:
    summary = summarize_fire_events(
        [
            FireEventRecord(0, 5.0),
            FireEventRecord(0, 20.0),
            FireEventRecord(2, 100.0),
            FireEventRecord(3, 1.0),
            FireEventRecord(3, 2.0),
        ],
        years=4,
        burnable_area_ha=1000.0,
        cell_size_ha=10.0,
        target=_target(),
        historical_sizes_ha=[5.0, 50.0, 100.0],
    )

    diagnostics = summary.diagnostics
    assert diagnostics is not None
    assert diagnostics.target_ignitions == pytest.approx(2.0)
    assert diagnostics.achieved_ignitions == pytest.approx(1.25)
    assert diagnostics.target_escapes == pytest.approx(1.0)
    assert diagnostics.achieved_escapes == pytest.approx(0.5)
    assert diagnostics.model_mean_size_ha == pytest.approx(60.0)
    assert diagnostics.historical_mean_size_ha == pytest.approx(75.0)
    assert diagnostics.historical_median_size_ha == pytest.approx(75.0)
    # The scfm diagnostic FRI uses escaped fires only (20 + 100 ha), not all 128 ha.
    assert diagnostics.achieved_fri_years == pytest.approx(4.0 / (120.0 / 1000.0))
    assert diagnostics.target_fri_years == pytest.approx(50.0)


def test_event_log_extraction_and_scenario_summary() -> None:
    log = _log(
        (
            _event("a", 0, 5.0),
            _event("b", 0, 20.0),
            _event("c", 1, None, event_type="succession"),
            _event("d", 2, 100.0),
        )
    )

    records = events_from_log(log)
    assert [record.area_ha for record in records] == [5.0, 20.0, 100.0]
    summary = summarize_event_log(log, years=3, burnable_area_ha=1000.0, cell_size_ha=10.0)
    assert summary.total_burned_ha == pytest.approx(125.0)
    assert summary.burn_probability == pytest.approx(2.0 / 3.0)

    summaries = summarize_event_logs(
        (log, _log((_event("e", 0, 10.0),), scenario="other")),
        years=3,
        burnable_area_ha=1000.0,
        cell_size_ha=10.0,
    )
    assert sorted(summaries) == ["other", "toy"]
    assert summaries["other"].total_burned_ha == pytest.approx(10.0)


def test_zero_fire_summary_is_well_defined() -> None:
    summary = summarize_fire_events(
        [],
        years=3,
        burnable_area_ha=100.0,
        cell_size_ha=5.0,
        target=_target(),
        historical_sizes_ha=[5.0, 50.0, 100.0],
    )

    assert summary.total_burned_ha == 0.0
    assert summary.burn_probability == 0.0
    assert summary.annual_burn_rate == 0.0
    assert summary.fire_return_interval_years is None
    assert summary.mean_fire_size_ha == 0.0
    assert summary.p90_fire_size_ha == 0.0
    assert summary.diagnostics is None


def test_summary_serializes_to_json() -> None:
    summary = summarize_fire_events(
        [FireEventRecord(0, 12.0)],
        years=1,
        burnable_area_ha=100.0,
        cell_size_ha=5.0,
    )

    payload = summary.to_dict()
    assert payload["schema_version"] == FIRE_RISK_VERSION
    encoded = json.dumps(payload, allow_nan=False)
    assert '"fire_return_interval_years": 8.333333333333334' in encoded


def test_invalid_inputs_fail_loudly() -> None:
    with pytest.raises(FireRiskError, match="years"):
        summarize_fire_events([], years=0, burnable_area_ha=1.0, cell_size_ha=1.0)
    with pytest.raises(FireRiskError, match="burnable_area_ha"):
        summarize_fire_events([], years=1, burnable_area_ha=0.0, cell_size_ha=1.0)
    with pytest.raises(FireRiskError, match="historical_sizes_ha"):
        summarize_fire_events(
            [],
            years=1,
            burnable_area_ha=1.0,
            cell_size_ha=1.0,
            target=_target(),
        )
    with pytest.raises(FireRiskError, match="outside"):
        summarize_fire_events(
            [FireEventRecord(2, 1.0)],
            years=2,
            burnable_area_ha=1.0,
            cell_size_ha=1.0,
        )
    with pytest.raises(FireRiskError, match="area_ha"):
        FireEventRecord(0, math.nan)
    with pytest.raises(FireRiskError, match="area_ha"):
        events_from_log(_log((_event("a", 0, None),)))
    with pytest.raises(FireRiskError, match="duplicate"):
        summarize_event_logs(
            (_log((_event("a", 0, 1.0),)), _log((_event("b", 0, 1.0),))),
            years=1,
            burnable_area_ha=1.0,
            cell_size_ha=1.0,
        )
