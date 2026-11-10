"""Tests for the Hay River / K'atl'odeeche second-fire fixture."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.fire.comparison import observed_mask, run_observed_case
from ws4.fire.observed import load_hay_river

FIXTURE = Path(__file__).parent / "fixtures" / "fire" / "hay_river_2023"


def test_load_hay_river_fixture() -> None:
    fire = load_hay_river(FIXTURE)

    assert fire.fire_id == "2023_320"
    assert fire.grid.ncols == 131
    assert fire.grid.nrows == 117
    assert len(fire.perimeters) == 7
    assert len(fire.weather) == 156
    assert fire.event_start.isoformat() == "2023-05-14T12:00:00"
    assert fire.event_end.isoformat() == "2023-05-20T23:00:00"
    assert fire.grid.contains(*fire.ignition_xy)


def test_hay_river_perimeters_are_cumulative() -> None:
    fire = load_hay_river(FIXTURE)

    start = observed_mask(fire, 0)
    final = observed_mask(fire, -1)

    cell_area_ha = fire.grid.cell_size_m**2 / 10_000.0
    assert start.sum() * cell_area_ha == pytest.approx(29.0)
    assert final.sum() * cell_area_ha == pytest.approx(2987.0)


def test_hay_river_weather_is_hourly_and_covered() -> None:
    fire = load_hay_river(FIXTURE)

    diffs = fire.weather["local_time"].diff().dropna()
    assert (diffs == pd.Timedelta(hours=1)).all()
    assert fire.weather["local_time"].min().isoformat() == "2023-05-14T12:00:00"
    assert fire.weather["local_time"].max().isoformat() == "2023-05-20T23:00:00"


def test_hay_river_summary_is_json_ready() -> None:
    fire = load_hay_river(FIXTURE)

    summary = fire.to_dict()

    assert summary["fire_id"] == "2023_320"
    assert summary["weather_rows"] == 156
    perimeters = summary["perimeters"]
    assert isinstance(perimeters, list)
    first = perimeters[0]
    last = perimeters[-1]
    assert isinstance(first, dict)
    assert isinstance(last, dict)
    assert str(first["observed_at"]).startswith("2023-05-14")
    assert str(last["observed_at"]).startswith("2023-05-20")
    provenance = summary["provenance"]
    assert isinstance(provenance, dict)
    assert provenance["fire_id"] == "2023_320"


def test_hay_river_case_uses_calibration_multipliers() -> None:
    """The generic runner passes the registered multipliers to growth."""
    fire = load_hay_river(FIXTURE)
    case = run_observed_case(
        fire,
        scenario="multiplier-test",
        ffmc=92.92,
        bui=73.28,
        duration_min=60.0,
        wind_multiplier=0.85,
        head_ros_multiplier=0.75,
    )

    assert case.growth.config.wind_multiplier == pytest.approx(0.85)
    assert case.growth.config.head_ros_multiplier == pytest.approx(0.75)
    assert 0.0 <= case.metrics.iou <= 1.0
