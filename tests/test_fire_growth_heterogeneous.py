"""Tests for per-cell fuel and terrain in the Huygens growth engine."""

from __future__ import annotations

import numpy as np
import pytest
from ws4.fire.benchmark import compare_growth_to_ellipse, ellipse_metrics
from ws4.fire.crown import fbp_crown_fire
from ws4.fire.fuel import FireFuelError
from ws4.fire.growth import (
    GrowthConfig,
    SiteGrid,
    WeatherStep,
    effective_wind,
    grow_fire,
    length_to_breadth,
    slope_aspect_from_elevation,
)


def _constant_grid(fuel: str = "C2", rows: int = 25, cols: int = 25) -> SiteGrid:
    """Return a heterogeneous grid filled with one fuel and flat terrain."""
    fuel_grid = np.full((rows, cols), fuel, dtype=object)
    return SiteGrid(
        fuel_type=fuel,
        rows=rows,
        cols=cols,
        cell_size_m=10.0,
        ffmc=90.0,
        bui=40.0,
        wind_kmh=15.0,
        wind_direction_deg=270.0,
        slope_percent=0.0,
        aspect_deg=0.0,
        fuel_type_grid=fuel_grid,
        slope_percent_grid=np.zeros((rows, cols)),
        aspect_deg_grid=np.zeros((rows, cols)),
        elevation_m_grid=np.full((rows, cols), 500.0),
    )


def _config(rows: int = 25, cols: int = 25, minutes: float = 30.0) -> GrowthConfig:
    """Return a centered ignition configuration."""
    return GrowthConfig(
        ignition_cells=((rows // 2, cols // 2),),
        max_time_min=minutes,
        snapshot_interval_min=minutes,
        neighbor_radius=2,
    )


def test_constant_heterogeneous_grid_matches_the_homogeneous_engine() -> None:
    homogeneous = SiteGrid(
        fuel_type="C2",
        rows=25,
        cols=25,
        cell_size_m=10.0,
        ffmc=90.0,
        bui=40.0,
        wind_kmh=15.0,
        wind_direction_deg=270.0,
        slope_percent=0.0,
        aspect_deg=0.0,
        elevation_m=500.0,
    )

    expected = grow_fire(homogeneous, _config())
    actual = grow_fire(_constant_grid(), _config())

    assert np.array_equal(
        np.isfinite(expected.ignition_time_min), np.isfinite(actual.ignition_time_min)
    )
    assert np.allclose(
        expected.ignition_time_min[np.isfinite(expected.ignition_time_min)],
        actual.ignition_time_min[np.isfinite(actual.ignition_time_min)],
    )
    assert actual.burned_area_ha == pytest.approx(expected.burned_area_ha)
    assert actual.perimeter_m == pytest.approx(expected.perimeter_m)


def test_two_fuel_grid_changes_local_head_ros_and_geometry() -> None:
    fuel_grid = np.full((20, 20), "C2", dtype=object)
    fuel_grid[:, 10:] = "C1"

    grid = SiteGrid(
        fuel_type="C2",
        rows=20,
        cols=20,
        cell_size_m=10.0,
        ffmc=90.0,
        bui=40.0,
        wind_kmh=15.0,
        wind_direction_deg=270.0,
        slope_percent=0.0,
        aspect_deg=0.0,
        fuel_type_grid=fuel_grid,
        slope_percent_grid=np.zeros((20, 20)),
        aspect_deg_grid=np.zeros((20, 20)),
        elevation_m_grid=np.full((20, 20), 500.0),
    )
    result = grow_fire(grid, _config(rows=20, cols=20, minutes=20.0))

    assert result.head_ros_grid is not None
    assert result.head_ros_grid[0, 0] > result.head_ros_grid[0, -1]
    assert result.head_ros_grid[0, 0] != result.head_ros_grid[0, -1]
    assert result.summary()["fuel_type"] == "heterogeneous"


def test_per_cell_head_ros_matches_the_fbp_kernel() -> None:
    grid = _constant_grid()
    result = grow_fire(grid, _config(minutes=5.0))
    wind = effective_wind("C2", 90.0, 40.0, 15.0, 270.0, 0.0, 0.0)
    crown = fbp_crown_fire(
        "C2",
        90.0,
        40.0,
        wind.speed_kmh,
        elevation_m=500.0,
        conifer_percent=50.0,
        dead_fir_percent=35.0,
        crown_closure_percent=80.0,
    )

    assert result.head_ros_grid is not None
    assert result.length_to_breadth_grid is not None
    assert result.spread_azimuth_deg_grid is not None
    assert result.head_ros_grid[12, 12] == pytest.approx(crown.rate_of_spread_m_min)
    assert result.length_to_breadth_grid[12, 12] == pytest.approx(
        length_to_breadth("C2", wind.speed_kmh)
    )
    assert result.spread_azimuth_deg_grid[12, 12] == pytest.approx(wind.azimuth_deg)


def test_terrain_grid_changes_head_ros() -> None:
    grid = _constant_grid()
    flat = grow_fire(grid, _config(minutes=5.0))
    sloped = SiteGrid(
        fuel_type="C2",
        rows=25,
        cols=25,
        cell_size_m=10.0,
        ffmc=90.0,
        bui=40.0,
        wind_kmh=15.0,
        wind_direction_deg=270.0,
        slope_percent=0.0,
        aspect_deg=180.0,
        fuel_type_grid=np.full((25, 25), "C2", dtype=object),
        slope_percent_grid=np.full((25, 25), 35.0),
        aspect_deg_grid=np.full((25, 25), 180.0),
        elevation_m_grid=np.linspace(500.0, 900.0, 25 * 25).reshape(25, 25),
    )
    steep = grow_fire(sloped, _config(minutes=5.0))

    assert flat.head_ros_grid is not None
    assert steep.head_ros_grid is not None
    assert steep.head_ros_grid[12, 12] > flat.head_ros_grid[12, 12]


def test_bad_grid_shape_fails() -> None:
    with pytest.raises(FireFuelError, match="fuel_type_grid"):
        SiteGrid(
            fuel_type="C2",
            rows=3,
            cols=3,
            cell_size_m=10.0,
            ffmc=90.0,
            bui=40.0,
            wind_kmh=15.0,
            wind_direction_deg=270.0,
            slope_percent=0.0,
            aspect_deg=0.0,
            fuel_type_grid=np.full((2, 2), "C2", dtype=object),
        )


def test_slope_aspect_follows_the_north_first_elevation_grid() -> None:
    elevation = np.tile(np.arange(5, dtype=float) * 5.0, (5, 1))
    slope, aspect = slope_aspect_from_elevation(elevation, 10.0)

    assert slope[2, 2] == pytest.approx(50.0)
    assert aspect[2, 2] == pytest.approx(270.0)


def test_flat_elevation_has_zero_slope_and_aspect() -> None:
    elevation = np.full((5, 5), 800.0)
    slope, aspect = slope_aspect_from_elevation(elevation, 10.0)

    assert np.allclose(slope, 0.0)
    assert np.allclose(aspect, 0.0)


def test_bad_elevation_grid_fails() -> None:
    with pytest.raises(FireFuelError, match="two-dimensional"):
        slope_aspect_from_elevation(np.zeros(5), 10.0)


def test_constant_heterogeneous_grid_preserves_the_analytic_ellipse() -> None:
    grid = SiteGrid(
        fuel_type="C2",
        rows=201,
        cols=201,
        cell_size_m=10.0,
        ffmc=90.0,
        bui=40.0,
        wind_kmh=15.0,
        wind_direction_deg=270.0,
        slope_percent=0.0,
        aspect_deg=0.0,
        fuel_type_grid=np.full((201, 201), "C2", dtype=object),
        slope_percent_grid=np.zeros((201, 201)),
        aspect_deg_grid=np.zeros((201, 201)),
        elevation_m_grid=np.full((201, 201), 500.0),
    )
    result = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((100, 100),),
            max_time_min=60.0,
            snapshot_interval_min=60.0,
            neighbor_radius=2,
        ),
    )
    expected = ellipse_metrics(result.head_ros_m_min, result.length_to_breadth, 60.0)
    comparison = compare_growth_to_ellipse(result, expected)

    assert abs(comparison.area_relative_error) < 0.1
    assert abs(comparison.perimeter_relative_error) < 0.3


def test_constant_weather_steps_match_the_static_run() -> None:
    static = grow_fire(_constant_grid(), _config(minutes=20.0))
    dynamic = grow_fire(
        _constant_grid(),
        GrowthConfig(
            ignition_cells=((12, 12),),
            max_time_min=20.0,
            snapshot_interval_min=20.0,
            neighbor_radius=2,
            weather_steps=(WeatherStep(0.0, 15.0, 270.0, ffmc=90.0, bui=40.0),),
        ),
    )

    assert np.array_equal(
        np.isfinite(static.ignition_time_min), np.isfinite(dynamic.ignition_time_min)
    )
    assert np.allclose(
        static.ignition_time_min[np.isfinite(static.ignition_time_min)],
        dynamic.ignition_time_min[np.isfinite(dynamic.ignition_time_min)],
    )
    assert dynamic.summary()["weather_mode"] == "time_dependent"


def test_a_wind_shift_delays_a_far_eastern_arrival() -> None:
    grid = _constant_grid(rows=101, cols=101)
    static = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((50, 50),),
            max_time_min=180.0,
            snapshot_interval_min=180.0,
            neighbor_radius=2,
        ),
    )
    shifted = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((50, 50),),
            max_time_min=180.0,
            snapshot_interval_min=180.0,
            neighbor_radius=2,
            weather_steps=(
                WeatherStep(0.0, 20.0, 270.0, ffmc=90.0, bui=40.0),
                WeatherStep(10.0, 0.0, 270.0, ffmc=90.0, bui=40.0),
            ),
        ),
    )

    static_arrival = static.ignition_time_min[50, 90]
    shifted_arrival = shifted.ignition_time_min[50, 90]
    assert np.isfinite(static_arrival)
    assert np.isfinite(shifted_arrival)
    assert shifted_arrival > static_arrival


def test_weather_steps_must_start_at_zero_and_be_ordered() -> None:
    with pytest.raises(FireFuelError, match="start at 0"):
        GrowthConfig(ignition_cells=((0, 0),), weather_steps=(WeatherStep(1.0, 10.0, 270.0),))
    with pytest.raises(FireFuelError, match="ordered"):
        GrowthConfig(
            ignition_cells=((0, 0),),
            weather_steps=(
                WeatherStep(0.0, 10.0, 270.0),
                WeatherStep(0.0, 20.0, 270.0),
            ),
        )


def test_weather_step_rejects_invalid_values() -> None:
    with pytest.raises(FireFuelError):
        WeatherStep(-1.0, 10.0, 270.0)
    with pytest.raises(FireFuelError):
        WeatherStep(0.0, 10.0, 270.0, ffmc=102.0)
    with pytest.raises(FireFuelError):
        WeatherStep(0.0, 10.0, 270.0, bui=-1.0)
    with pytest.raises(FireFuelError, match="must not be empty"):
        GrowthConfig(ignition_cells=((0, 0),), weather_steps=())


def test_terrain_grid_rejects_a_bad_shape() -> None:
    with pytest.raises(FireFuelError, match="slope_percent_grid"):
        SiteGrid(
            fuel_type="C2",
            rows=3,
            cols=3,
            cell_size_m=10.0,
            ffmc=90.0,
            bui=40.0,
            wind_kmh=15.0,
            wind_direction_deg=270.0,
            slope_percent=0.0,
            aspect_deg=0.0,
            slope_percent_grid=np.zeros((2, 2)),
        )


def test_nodata_elevation_is_filled_and_masked() -> None:
    elevation = np.full((5, 5), 800.0)
    elevation[0, 0] = -9999.0
    slope, aspect = slope_aspect_from_elevation(elevation, 10.0, nodata=-9999.0)

    assert slope[0, 0] == 0.0
    assert aspect[0, 0] == 0.0
    assert np.isfinite(slope).all()


def test_elevation_with_no_valid_cells_fails() -> None:
    with pytest.raises(FireFuelError, match="no valid cells"):
        slope_aspect_from_elevation(np.full((3, 3), -9999.0), 10.0, nodata=-9999.0)
