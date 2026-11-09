"""Tests for the P161 calibration grid and weighted score."""

from __future__ import annotations

import pytest
from ws4.fire.calibration import (
    CalibrationParameters,
    calibration_score,
    is_within_protocol,
    parameter_grid,
)
from ws4.fire.comparison import PerimeterMetrics
from ws4.fire.fuel import FireFuelError


def _metrics() -> PerimeterMetrics:
    """Return a fixed metric record for score arithmetic."""
    return PerimeterMetrics(
        area_sim_ha=120.0,
        area_obs_ha=100.0,
        area_bias=0.2,
        perimeter_sim_m=115.0,
        perimeter_obs_m=100.0,
        perimeter_bias=0.15,
        centroid_distance_m=2000.0,
        iou=0.8,
        sorensen=0.9,
        orientation_error_deg=15.0,
    )


def test_calibration_score_uses_registered_weights() -> None:
    """The score components match the pre-registered formula."""
    score = calibration_score(_metrics())

    assert score.area == pytest.approx(0.25 * 0.2)
    assert score.perimeter == pytest.approx(0.15 * 0.15)
    assert score.centroid == pytest.approx(0.20 * 0.4)
    assert score.iou == pytest.approx(0.20 * 0.2)
    assert score.sorensen == pytest.approx(0.10 * 0.1)
    assert score.orientation == pytest.approx(0.10 * 0.5)
    assert score.total == pytest.approx(
        sum(
            score.to_dict()[key]
            for key in ("area", "perimeter", "centroid", "iou", "sorensen", "orientation")
        )
    )


def test_calibration_score_caps_centroid_and_orientation() -> None:
    """The centroid and orientation terms do not exceed their caps."""
    metrics = PerimeterMetrics(
        area_sim_ha=100.0,
        area_obs_ha=100.0,
        area_bias=0.0,
        perimeter_sim_m=100.0,
        perimeter_obs_m=100.0,
        perimeter_bias=0.0,
        centroid_distance_m=50_000.0,
        iou=1.0,
        sorensen=1.0,
        orientation_error_deg=90.0,
    )

    score = calibration_score(metrics)

    assert score.centroid == pytest.approx(0.20)
    assert score.orientation == pytest.approx(0.10)


def test_parameter_grid_is_the_registered_25_points() -> None:
    """The grid has 25 points, includes the baseline, and stays in bounds."""
    grid = parameter_grid()

    assert len(grid) == 25
    assert CalibrationParameters(1.0, 1.0) in grid
    assert all(is_within_protocol(point) for point in grid)
    assert {point.wind_multiplier for point in grid} == {0.70, 0.85, 1.00, 1.15, 1.30}
    assert {point.head_ros_multiplier for point in grid} == {0.50, 0.75, 1.00, 1.25, 1.50}


def test_parameters_reject_non_positive_multipliers() -> None:
    """The parameter object rejects invalid multipliers."""
    with pytest.raises(FireFuelError, match="wind_multiplier"):
        CalibrationParameters(wind_multiplier=0.0)
    with pytest.raises(FireFuelError, match="head_ros_multiplier"):
        CalibrationParameters(head_ros_multiplier=-1.0)


def test_protocol_bounds_are_exclusive_checks() -> None:
    """The bound check accepts the boundary and rejects outside points."""
    assert is_within_protocol(CalibrationParameters(0.70, 0.50))
    assert is_within_protocol(CalibrationParameters(1.30, 1.50))
    assert not is_within_protocol(CalibrationParameters(0.69, 1.0))
    assert not is_within_protocol(CalibrationParameters(1.0, 1.51))


def test_growth_multipliers_change_spread() -> None:
    """The head-ROS multiplier changes growth without changing inputs."""
    from ws4.fire.growth import GrowthConfig, SiteGrid, WeatherStep, grow_fire

    grid = SiteGrid(
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
    steps = (WeatherStep(0.0, 15.0, 270.0, ffmc=90.0, bui=60.0),)
    baseline = grow_fire(
        grid,
        GrowthConfig(ignition_cells=((20, 20),), max_time_min=60.0, weather_steps=steps),
    )
    reduced = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((20, 20),),
            max_time_min=60.0,
            weather_steps=steps,
            head_ros_multiplier=0.5,
        ),
    )

    assert reduced.burned_area_ha < baseline.burned_area_ha
    assert reduced.config.head_ros_multiplier == pytest.approx(0.5)
