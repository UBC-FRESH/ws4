"""Tests for the FBP ellipse benchmark and the scenario ensemble."""

from __future__ import annotations

import math

import pandas as pd
import pytest
from ws4.fire.benchmark import (
    MAX_BENCHMARK_CELLS,
    EllipseMetrics,
    WeatherScenario,
    compare_growth_to_ellipse,
    ellipse_metrics,
    run_growth_ensemble,
    summarize_ensemble,
)
from ws4.fire.fuel import FireFuelError
from ws4.fire.growth import GrowthConfig, SiteGrid, grow_fire


def test_circle_ellipse_matches_the_analytic_circle() -> None:
    metrics = ellipse_metrics(10.0, 1.0, 10.0)

    assert metrics.head_distance_m == pytest.approx(100.0)
    assert metrics.back_distance_m == pytest.approx(100.0)
    assert metrics.length_m == pytest.approx(200.0)
    assert metrics.width_m == pytest.approx(200.0)
    assert metrics.area_ha == pytest.approx(math.pi)
    assert metrics.perimeter_m == pytest.approx(200.0 * math.pi)


def test_ellipse_axes_follow_the_length_to_breadth_ratio() -> None:
    metrics = ellipse_metrics(10.0, 3.0, 10.0)

    assert metrics.length_m > metrics.width_m
    assert metrics.length_to_breadth == pytest.approx(3.0)
    assert metrics.area_ha > 0.0
    expected_width = metrics.length_m * math.sqrt(1.0 - 0.8**2)
    assert metrics.width_m == pytest.approx(expected_width)


def test_zero_ros_is_an_empty_ellipse() -> None:
    metrics = ellipse_metrics(0.0, 2.0, 30.0)
    assert metrics.area_ha == 0.0
    assert metrics.perimeter_m == 0.0


def test_growth_comparison_is_close_on_a_small_circle() -> None:
    grid = SiteGrid(
        fuel_type="C2",
        rows=201,
        cols=201,
        cell_size_m=10.0,
        ffmc=90.0,
        bui=60.0,
        wind_kmh=0.0,
        wind_direction_deg=0.0,
        slope_percent=0.0,
        aspect_deg=0.0,
    )
    result = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((100, 100),),
            max_time_min=30.0,
            snapshot_interval_min=30.0,
        ),
    )
    expected = ellipse_metrics(result.head_ros_m_min, 1.0, 30.0)
    comparison = compare_growth_to_ellipse(result, expected)

    assert abs(comparison.length_relative_error) < 0.1
    assert abs(comparison.width_relative_error) < 0.1
    assert abs(comparison.area_relative_error) < 0.1
    assert abs(comparison.perimeter_relative_error) < 0.3


def test_ensemble_runs_and_summarizes() -> None:
    scenarios = [
        WeatherScenario("low", "C2", 85.0, 30.0, 5.0, duration_min=30.0),
        WeatherScenario("high", "C2", 95.0, 90.0, 20.0, duration_min=30.0),
    ]
    frame = run_growth_ensemble(scenarios, cell_size_m=20.0)

    assert set(frame["scenario_id"]) == {"low", "high"}
    assert (frame["measured_area_ha"] > 0.0).all()
    assert (frame["area_relative_error"].abs() < 0.15).all()
    summary = summarize_ensemble(frame, thresholds=(0.5, 2.0))
    assert summary["count"] == 2
    exceedance = summary["p_area_ge_0.5"]
    median = summary["p50"]
    assert isinstance(exceedance, float)
    assert isinstance(median, float)
    assert 0.0 <= exceedance <= 1.0
    assert median > 0.0


def test_summary_quantiles_and_exceedance() -> None:
    frame = pd.DataFrame({"area_ha": [1.0, 2.0, 3.0, 4.0]})
    summary = summarize_ensemble(frame, thresholds=(2.5, 4.0), column="area_ha")

    assert summary["p10"] == pytest.approx(1.3)
    assert summary["p50"] == pytest.approx(2.5)
    assert summary["p90"] == pytest.approx(3.7)
    assert summary["p_area_ge_2.5"] == pytest.approx(0.5)
    assert summary["p_area_ge_4"] == pytest.approx(0.25)


def test_invalid_benchmark_inputs_fail_explicitly() -> None:
    with pytest.raises(FireFuelError, match="length_to_breadth"):
        ellipse_metrics(10.0, 0.5, 10.0)
    with pytest.raises(FireFuelError, match="head_ros_m_min"):
        ellipse_metrics(-1.0, 1.0, 10.0)
    with pytest.raises(FireFuelError, match="duration_min"):
        ellipse_metrics(10.0, 1.0, 0.0)
    with pytest.raises(FireFuelError, match="at least one scenario"):
        run_growth_ensemble([])
    with pytest.raises(FireFuelError, match="empty"):
        summarize_ensemble(pd.DataFrame({"area_ha": []}), thresholds=(1.0,), column="area_ha")
    with pytest.raises(FireFuelError, match="no 'area_ha' column"):
        summarize_ensemble(pd.DataFrame({"other": [1.0]}), thresholds=(1.0,), column="area_ha")
    with pytest.raises(FireFuelError, match="finite"):
        summarize_ensemble(
            pd.DataFrame({"area_ha": [1.0, math.inf]}), thresholds=(1.0,), column="area_ha"
        )
    huge = WeatherScenario("huge", "C2", 95.0, 90.0, 40.0, duration_min=10_000.0)
    with pytest.raises(FireFuelError, match="benchmark grid"):
        run_growth_ensemble([huge], cell_size_m=1.0)


def test_comparison_rejects_wrong_types() -> None:
    expected = EllipseMetrics(1.0, 1.0, 1.0, 1.0, 1.0, 2.0, 2.0, 0.1, 6.0)
    grid = SiteGrid("C2", 21, 21, 10.0, 90.0, 60.0, 0.0, 0.0, 0.0, 0.0)
    result = grow_fire(
        grid,
        GrowthConfig(ignition_cells=((10, 10),), max_time_min=5.0, snapshot_interval_min=5.0),
    )
    with pytest.raises(FireFuelError, match="result"):
        compare_growth_to_ellipse(object(), expected)  # type: ignore[arg-type]
    with pytest.raises(FireFuelError, match="expected"):
        compare_growth_to_ellipse(result, object())  # type: ignore[arg-type]


def test_benchmark_grid_guard_is_named() -> None:
    assert MAX_BENCHMARK_CELLS >= 101
