"""Tests for the seeded screening spotting model."""

from __future__ import annotations

import numpy as np
import pytest
from ws4.fire.fuel import FireFuelError
from ws4.fire.growth import (
    GrowthConfig,
    GrowthResult,
    SiteGrid,
    SpottingConfig,
    WeatherStep,
    grow_fire,
)


def _grid() -> SiteGrid:
    """Return a small homogeneous grid."""
    return SiteGrid(
        fuel_type="C2",
        rows=31,
        cols=31,
        cell_size_m=100.0,
        ffmc=90.0,
        bui=60.0,
        wind_kmh=20.0,
        wind_direction_deg=270.0,
        slope_percent=0.0,
        aspect_deg=0.0,
    )


def _grow(spotting: SpottingConfig | None) -> GrowthResult:
    """Grow one 90-minute fire."""
    return grow_fire(
        _grid(),
        GrowthConfig(
            ignition_cells=((15, 15),),
            max_time_min=90.0,
            snapshot_interval_min=90.0,
            weather_steps=(WeatherStep(0.0, 20.0, 270.0, ffmc=90.0, bui=60.0),),
            spotting=spotting,
        ),
    )


def test_spotting_is_off_by_default() -> None:
    """No spotting config produces no spot ignitions."""
    result = _grow(None)

    assert result.spot_ignitions == ()
    assert result.summary()["spot_ignitions"] == []


def test_spotting_is_seeded_and_bounded() -> None:
    """Spots replay exactly and land on burnable cells within bounds."""
    config = SpottingConfig(
        probability_per_cell_per_hour=1.0,
        min_distance_m=50.0,
        max_distance_m=150.0,
        interval_min=30.0,
        downwind_spread_deg=20.0,
        seed=5,
    )
    first = _grow(config)
    second = _grow(config)

    assert first.spot_ignitions
    assert first.spot_ignitions == second.spot_ignitions
    burnable = np.asarray(first.grid.burnable, dtype=bool)
    for spot in first.spot_ignitions:
        assert 50.0 <= spot.distance_m <= 150.0
        assert 0 <= spot.target_row < first.grid.rows
        assert 0 <= spot.target_col < first.grid.cols
        assert bool(burnable[spot.target_row, spot.target_col])
        assert spot.time_min >= 0.0
    recorded = first.summary()["spot_ignitions"]
    assert isinstance(recorded, list)
    assert len(recorded) == len(first.spot_ignitions)


def test_zero_probability_produces_no_spots() -> None:
    """A zero emission probability switches the process off."""
    result = _grow(
        SpottingConfig(
            probability_per_cell_per_hour=0.0,
            min_distance_m=50.0,
            max_distance_m=100.0,
            interval_min=30.0,
            seed=1,
        )
    )

    assert not result.spot_ignitions


def test_spotting_config_validates_and_requires_weather() -> None:
    """Bad distances and a static run are rejected."""
    with pytest.raises(FireFuelError, match="at least min"):
        SpottingConfig(min_distance_m=200.0, max_distance_m=100.0)
    with pytest.raises(FireFuelError, match="interval"):
        SpottingConfig(interval_min=0.0)
    with pytest.raises(FireFuelError, match="seed"):
        SpottingConfig(seed=1.5)  # type: ignore[arg-type]
    with pytest.raises(FireFuelError, match="weather_steps"):
        GrowthConfig(
            ignition_cells=((0, 0),),
            spotting=SpottingConfig(),
        )
