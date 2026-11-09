"""Tests for burning-condition gates on the fire growth path."""

from __future__ import annotations

import pytest
from ws4.fire.comparison import ComparisonError, dogrib_burning_conditions
from ws4.fire.fuel import FireFuelError
from ws4.fire.growth import BurningConditions, GrowthConfig, SiteGrid, WeatherStep, grow_fire


def _grid() -> SiteGrid:
    """Return a small homogeneous C2 grid for threshold tests."""
    return SiteGrid(
        fuel_type="C2",
        rows=41,
        cols=41,
        cell_size_m=10.0,
        ffmc=90.0,
        bui=60.0,
        wind_kmh=15.0,
        wind_direction_deg=270.0,
        slope_percent=0.0,
        aspect_deg=0.0,
    )


def _grow(conditions: BurningConditions | None) -> tuple[float, float]:
    """Grow one 120-minute fire and return its area and a downwind arrival time."""
    result = grow_fire(
        _grid(),
        GrowthConfig(
            ignition_cells=((20, 20),),
            max_time_min=120.0,
            snapshot_interval_min=120.0,
            neighbor_radius=2,
            weather_steps=(
                WeatherStep(
                    0.0,
                    20.0,
                    270.0,
                    ffmc=90.0,
                    bui=60.0,
                    relative_humidity_percent=40.0,
                ),
            ),
            burning_conditions=conditions,
        ),
    )
    return result.burned_area_ha, float(result.ignition_time_min[20, 30])


def test_thresholds_are_exclusive_at_the_boundary() -> None:
    """Boundary values do not pass a strict threshold."""
    conditions = BurningConditions(
        isi_gt=8.0,
        wind_gt_kmh=5.0,
        relative_humidity_lt_percent=50.0,
    )

    assert not conditions.allows(isi=8.0, wind_kmh=5.0, relative_humidity_percent=50.0)
    assert conditions.allows(isi=8.1, wind_kmh=5.1, relative_humidity_percent=49.9)


def test_relative_humidity_can_be_minimum_or_maximum() -> None:
    """The two humidity interpretations are both expressible."""
    below = BurningConditions(relative_humidity_lt_percent=50.0)
    above = BurningConditions(relative_humidity_gt_percent=50.0)

    assert below.allows(isi=10.0, wind_kmh=10.0, relative_humidity_percent=40.0)
    assert not below.allows(isi=10.0, wind_kmh=10.0, relative_humidity_percent=60.0)
    assert above.allows(isi=10.0, wind_kmh=10.0, relative_humidity_percent=60.0)
    assert not above.allows(isi=10.0, wind_kmh=10.0, relative_humidity_percent=40.0)


def test_threshold_object_rejects_invalid_configuration() -> None:
    """An empty, negative, or inverted threshold set is invalid."""
    with pytest.raises(FireFuelError, match="at least one"):
        BurningConditions()
    with pytest.raises(FireFuelError, match="non-negative"):
        BurningConditions(wind_gt_kmh=-1.0)
    with pytest.raises(FireFuelError, match="between 0 and 100"):
        BurningConditions(relative_humidity_lt_percent=101.0)
    with pytest.raises(FireFuelError, match="less than"):
        BurningConditions(
            relative_humidity_gt_percent=60.0,
            relative_humidity_lt_percent=40.0,
        )


def test_failed_conditions_stop_growth() -> None:
    """A threshold failure leaves only the ignition cell burned."""
    blocked = BurningConditions(wind_gt_kmh=100.0)

    area, _arrival = _grow(blocked)

    assert area == pytest.approx(0.01)


def test_conditions_allow_growth_when_met() -> None:
    """A passing threshold does not alter the growth path."""
    baseline_area, baseline_arrival = _grow(None)
    allowed_area, allowed_arrival = _grow(BurningConditions(wind_gt_kmh=5.0))

    assert allowed_area == pytest.approx(baseline_area)
    assert allowed_arrival == pytest.approx(baseline_arrival)


def test_a_temporary_threshold_failure_delays_spread() -> None:
    """A failed first step waits for a later passing step instead of ending the run."""
    result = grow_fire(
        _grid(),
        GrowthConfig(
            ignition_cells=((20, 20),),
            max_time_min=120.0,
            snapshot_interval_min=120.0,
            neighbor_radius=2,
            weather_steps=(
                WeatherStep(
                    0.0,
                    10.0,
                    270.0,
                    ffmc=90.0,
                    bui=60.0,
                    relative_humidity_percent=40.0,
                ),
                WeatherStep(
                    30.0,
                    20.0,
                    270.0,
                    ffmc=90.0,
                    bui=60.0,
                    relative_humidity_percent=40.0,
                ),
            ),
            burning_conditions=BurningConditions(wind_gt_kmh=15.0),
        ),
    )

    assert result.burned_area_ha > 0.01
    assert result.ignition_time_min[20, 30] >= 30.0


def test_conditions_require_weather_steps_and_humidity() -> None:
    """The gate cannot be evaluated without an hourly weather stream."""
    with pytest.raises(FireFuelError, match="require weather_steps"):
        GrowthConfig(
            ignition_cells=((0, 0),),
            burning_conditions=BurningConditions(wind_gt_kmh=5.0),
        )
    with pytest.raises(FireFuelError, match="relative_humidity_percent"):
        GrowthConfig(
            ignition_cells=((0, 0),),
            weather_steps=(WeatherStep(0.0, 10.0, 270.0),),
            burning_conditions=BurningConditions(wind_gt_kmh=5.0),
        )


def test_dogrib_thresholds_encode_both_humidity_readings() -> None:
    """The Dogrib helper records the source and both humidity interpretations."""
    below = dogrib_burning_conditions()
    above = dogrib_burning_conditions(relative_humidity="gt")

    assert below.isi_gt == pytest.approx(8.0)
    assert below.wind_gt_kmh == pytest.approx(5.0)
    assert below.relative_humidity_lt_percent == pytest.approx(50.0)
    assert above.relative_humidity_gt_percent == pytest.approx(50.0)
    assert "Dogrib_v624" in below.source
    with pytest.raises(ComparisonError, match=r"lt.*gt"):
        dogrib_burning_conditions(relative_humidity="bad")
