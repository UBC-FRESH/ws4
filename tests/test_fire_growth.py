"""Tests for the site grid, slope adjustment, and Huygens growth engine.

The effective-wind references were generated with the ``cffdrs`` R package. The growth
expectations are analytic/geometric: a circle without wind or slope, an ellipse elongated
downwind, a centroid displaced upslope, and a barrier that stops the front.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
import pytest
from ws4.fire.fuel import FireFuelError
from ws4.fire.growth import (
    GROWTH_MODEL_VERSION,
    EffectiveWind,
    GrowthConfig,
    SiteGrid,
    WeatherStep,
    directional_ros,
    effective_wind,
    fragment_ignition_events,
    fragment_ignition_times,
    grow_fire,
    length_to_breadth,
)

FIXTURES = Path(__file__).parent / "fixtures" / "fire"


def reference(name: str) -> list[dict[str, str]]:
    """Read one growth reference table."""
    with (FIXTURES / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def make_grid(rows: int = 81, cols: int = 81, **overrides: object) -> SiteGrid:
    """Build a C2 homogeneous grid with sensible defaults."""
    values: dict[str, object] = {
        "fuel_type": "C2",
        "rows": rows,
        "cols": cols,
        "cell_size_m": 10.0,
        "ffmc": 90.0,
        "bui": 60.0,
        "wind_kmh": 0.0,
        "wind_direction_deg": 0.0,
        "slope_percent": 0.0,
        "aspect_deg": 0.0,
    }
    values.update(overrides)
    return SiteGrid(**values)  # type: ignore[arg-type]


def test_effective_wind_matches_the_reference() -> None:
    for row in reference("fbp_slope_adjustment.csv"):
        result = effective_wind(
            row["FuelType"],
            float(row["FFMC"]),
            float(row["BUI"]),
            float(row["WS"]),
            float(row["WD"]),
            float(row["GS"]),
            float(row["Aspect"]),
        )
        difference = abs((result.azimuth_deg - float(row["RAZ"])) % 360.0)
        difference = min(difference, 360.0 - difference)
        assert result.speed_kmh == pytest.approx(float(row["WSV"]), abs=0.02)
        assert difference == pytest.approx(0.0, abs=0.1)


def test_length_to_breadth_grows_with_wind() -> None:
    assert length_to_breadth("C2", 0.0) == pytest.approx(1.0)
    assert length_to_breadth("C2", 20.0) > length_to_breadth("C2", 5.0)
    assert length_to_breadth("O1A", 0.0) == pytest.approx(1.0)
    assert length_to_breadth("O1A", 10.0) > 1.0


def test_no_wind_no_slope_grows_as_a_circle() -> None:
    grid = make_grid()
    result = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((40, 40),),
            max_time_min=120.0,
            snapshot_interval_min=60.0,
        ),
    )
    last = result.snapshots[-1]
    radius = math.sqrt(last.area_ha * 10_000.0 / math.pi)

    assert result.length_to_breadth == pytest.approx(1.0)
    assert last.area_ha > 0.0
    assert last.perimeter_m / (2.0 * math.pi * radius) == pytest.approx(1.0, abs=0.25)
    assert result.head_ros_m_min > 0.0


def test_wind_elongates_the_fire_downwind() -> None:
    grid = make_grid(
        rows=201,
        cols=201,
        wind_kmh=20.0,
        wind_direction_deg=270.0,
    )
    result = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((100, 100),),
            max_time_min=30.0,
            snapshot_interval_min=30.0,
        ),
    )
    burned = result.ignition_time_min <= 30.0
    rows, cols = np.where(burned)
    height = int(np.max(rows)) - int(np.min(rows)) + 1
    width = int(np.max(cols)) - int(np.min(cols)) + 1

    assert result.effective_wind.azimuth_deg == pytest.approx(90.0)
    assert width > height * 1.3
    assert float(np.mean(cols)) > 100.0
    assert abs(float(np.mean(rows)) - 100.0) < 10.0


def test_slope_moves_the_fire_upslope() -> None:
    grid = make_grid(
        rows=201,
        cols=201,
        wind_kmh=0.0,
        slope_percent=30.0,
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
    burned = result.ignition_time_min <= 30.0
    rows, _ = np.where(burned)

    assert result.effective_wind.azimuth_deg == pytest.approx(180.0)
    assert float(np.mean(rows)) > 100.0


def test_barrier_stops_the_front() -> None:
    mask = np.ones((81, 81), dtype=bool)
    mask[:, 40] = False
    grid = make_grid(burnable=mask)
    result = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((40, 20),),
            max_time_min=120.0,
            snapshot_interval_min=120.0,
        ),
    )
    burned = result.ignition_time_min <= 120.0
    _, cols = np.where(burned)

    assert int(np.max(cols)) < 40
    assert result.burned_area_ha > 0.0


def test_snapshots_are_monotone() -> None:
    grid = make_grid(
        rows=101,
        cols=101,
        wind_kmh=15.0,
        wind_direction_deg=270.0,
    )
    result = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((50, 50),),
            max_time_min=60.0,
            snapshot_interval_min=15.0,
        ),
    )
    areas = [snapshot.area_ha for snapshot in result.snapshots]
    perimeters = [snapshot.perimeter_m for snapshot in result.snapshots]

    assert areas == sorted(areas)
    assert perimeters == sorted(perimeters)
    assert result.summary()["snapshots"]


def test_c6_slope_is_explicitly_unsupported() -> None:
    with pytest.raises(FireFuelError, match="C6 slope"):
        effective_wind("C6", 90.0, 60.0, 10.0, 270.0, 20.0, 0.0)


def test_growth_rejects_bad_ignition_and_masks() -> None:
    grid = make_grid(rows=10, cols=10)
    with pytest.raises(FireFuelError, match="outside the grid"):
        grow_fire(grid, GrowthConfig(ignition_cells=((20, 20),)))
    empty = np.zeros((10, 10), dtype=bool)
    with pytest.raises(FireFuelError, match="no burnable cells"):
        grow_fire(
            make_grid(rows=10, cols=10, burnable=empty),
            GrowthConfig(ignition_cells=((1, 1),)),
        )
    one_off = np.ones((10, 10), dtype=bool)
    one_off[1, 1] = False
    with pytest.raises(FireFuelError, match="unburnable"):
        grow_fire(
            make_grid(rows=10, cols=10, burnable=one_off),
            GrowthConfig(ignition_cells=((1, 1),)),
        )


def test_effective_wind_dataclass_serializes() -> None:
    wind = EffectiveWind(10.0, 180.0)
    assert wind.speed_kmh == 10.0
    assert wind.azimuth_deg == 180.0


def test_flat_wind_shape_matches_the_analytic_ellipse() -> None:
    grid = make_grid(
        rows=201,
        cols=201,
        wind_kmh=20.0,
        wind_direction_deg=270.0,
    )
    result = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((100, 100),),
            max_time_min=30.0,
            snapshot_interval_min=30.0,
        ),
    )
    burned = result.ignition_time_min <= 30.0
    rows, cols = np.where(burned)
    measured_length = (int(np.max(cols)) - int(np.min(cols)) + 1) * grid.cell_size_m
    measured_width = (int(np.max(rows)) - int(np.min(rows)) + 1) * grid.cell_size_m
    eccentricity = (result.length_to_breadth**2 - 1.0) / (result.length_to_breadth**2 + 1.0)
    head_distance = result.head_ros_m_min * 30.0
    back_distance = head_distance * (1.0 - eccentricity) / (1.0 + eccentricity)
    expected_length = head_distance + back_distance
    expected_width = expected_length * math.sqrt(1.0 - eccentricity**2)

    assert measured_length == pytest.approx(expected_length, rel=0.1)
    assert measured_width == pytest.approx(expected_width, rel=0.1)


def test_wind_and_slope_combine_into_one_vector() -> None:
    grid = make_grid(
        rows=201,
        cols=201,
        wind_kmh=15.0,
        wind_direction_deg=270.0,
        slope_percent=30.0,
        aspect_deg=180.0,
    )
    result = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((100, 100),),
            max_time_min=30.0,
            snapshot_interval_min=30.0,
        ),
    )
    burned = result.ignition_time_min <= 30.0
    rows, cols = np.where(burned)

    assert 0.0 < result.effective_wind.azimuth_deg < 90.0
    assert float(np.mean(rows)) < 100.0
    assert float(np.mean(cols)) > 100.0


def test_fragment_bridge_matches_the_growth_front() -> None:
    grid = make_grid(rows=41, cols=41, wind_kmh=20.0, wind_direction_deg=270.0)
    result = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((20, 5),),
            max_time_min=60.0,
            snapshot_interval_min=60.0,
        ),
    )
    fragments = np.ones((41, 41), dtype=int)
    fragments[:, 20:] = 2
    entries = fragment_ignition_times(result, fragments)

    assert [entry.fragment_id for entry in entries] == [1, 2]
    for entry in entries:
        cells = (fragments == entry.fragment_id) & np.isfinite(result.ignition_time_min)
        assert entry.ignition_time_min == pytest.approx(
            float(np.min(result.ignition_time_min[cells]))
        )
        assert entry.burned_cells == int(cells.sum())
        assert entry.area_ha == pytest.approx(entry.burned_cells * grid.cell_area_ha)
    assert sum(entry.area_ha for entry in entries) == pytest.approx(result.burned_area_ha)

    events = fragment_ignition_events(result, fragments, scenario_id="test", year=2024)
    assert len(events) == 2
    assert events[0].fragment_ids == (1,)
    assert events[0].year == 2024
    assert events[0].event_type == "fire_ignition"
    assert events[0].phase == "ignition"
    assert events[0].time == pytest.approx(2024.0 + entries[0].ignition_time_min / 525_600.0)
    attributes = dict(events[0].attributes)
    assert attributes["growth_model"] == GROWTH_MODEL_VERSION
    assert attributes["ignition_time_min"] == pytest.approx(entries[0].ignition_time_min)
    assert attributes["head_ros_m_min"] == pytest.approx(result.head_ros_m_min)
    assert len({event.event_id for event in events}) == 2


def test_fragment_bridge_rejects_bad_grids_and_time_spans() -> None:
    grid = make_grid(rows=41, cols=41, wind_kmh=20.0, wind_direction_deg=270.0)
    result = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((20, 5),),
            max_time_min=60.0,
            snapshot_interval_min=60.0,
        ),
    )
    with pytest.raises(FireFuelError, match="same shape"):
        fragment_ignition_times(result, np.ones((10, 10), dtype=int))
    with pytest.raises(FireFuelError, match="integer"):
        fragment_ignition_times(result, np.ones((41, 41), dtype=float))
    negative = np.ones((41, 41), dtype=int)
    negative[0, 0] = -1
    with pytest.raises(FireFuelError, match="non-negative"):
        fragment_ignition_times(result, negative)
    fragments = np.ones((41, 41), dtype=int)
    fragments[:, 20:] = 2
    with pytest.raises(FireFuelError, match="more than one"):
        fragment_ignition_events(result, fragments, minutes_per_year=1.0)


def test_directional_ros_matches_the_ellipse_template() -> None:
    """The public directional ROS is the head value and falls toward the back."""
    assert directional_ros(10.0, 1.0, 90.0) == pytest.approx(10.0)
    assert directional_ros(10.0, 3.0, 0.0) == pytest.approx(10.0)
    assert directional_ros(10.0, 3.0, 180.0) < directional_ros(10.0, 3.0, 90.0)


def test_containment_closure_blocks_a_target_at_arrival() -> None:
    grid = make_grid(rows=9, cols=9)
    closure = np.full((9, 9), np.inf)
    closure[4, 5] = 0.0
    weather = (
        WeatherStep(
            start_min=0.0,
            wind_kmh=0.0,
            wind_direction_deg=0.0,
            ffmc=90.0,
            bui=60.0,
            relative_humidity_percent=40.0,
        ),
    )
    result = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((4, 4),),
            max_time_min=60.0,
            snapshot_interval_min=60.0,
            weather_steps=weather,
            containment_start_min=closure,
        ),
    )
    assert not np.isfinite(result.ignition_time_min[4, 5])
    assert np.isfinite(result.ignition_time_min[4, 4])
    assert np.isfinite(result.ignition_time_min[3, 4])


def test_containment_closure_requires_matching_shape() -> None:
    grid = make_grid(rows=5, cols=5)
    with pytest.raises(FireFuelError, match="containment_start_min shape"):
        grow_fire(
            grid,
            GrowthConfig(
                ignition_cells=((2, 2),),
                max_time_min=30.0,
                containment_start_min=np.full((4, 4), np.inf),
            ),
        )


def test_containment_closure_blocks_jumping_over_a_closed_gap() -> None:
    grid = make_grid(rows=9, cols=9)
    burnable = np.ones((9, 9), dtype=bool)
    burnable[:, 4] = False
    burnable[4, 4] = True
    grid = make_grid(rows=9, cols=9, burnable=burnable)
    closure = np.full((9, 9), np.inf)
    closure[4, 4] = 0.0
    weather = (
        WeatherStep(
            start_min=0.0,
            wind_kmh=0.0,
            wind_direction_deg=0.0,
            ffmc=90.0,
            bui=60.0,
            relative_humidity_percent=40.0,
        ),
    )
    result = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((4, 1),),
            max_time_min=60.0,
            snapshot_interval_min=60.0,
            weather_steps=weather,
            containment_start_min=closure,
        ),
    )
    assert not np.isfinite(result.ignition_time_min[:, 5:]).any()


def test_rain_stopping_threshold_halts_growth() -> None:
    grid = make_grid(rows=61, cols=61)
    weather = (
        WeatherStep(
            start_min=0.0,
            wind_kmh=0.0,
            wind_direction_deg=0.0,
            ffmc=90.0,
            bui=60.0,
            relative_humidity_percent=40.0,
            precipitation_mm=0.0,
        ),
        WeatherStep(
            start_min=60.0,
            wind_kmh=0.0,
            wind_direction_deg=0.0,
            ffmc=90.0,
            bui=60.0,
            relative_humidity_percent=40.0,
            precipitation_mm=20.0,
        ),
    )
    free = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((30, 30),),
            max_time_min=600.0,
            snapshot_interval_min=60.0,
            weather_steps=weather,
        ),
    )
    stopped = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((30, 30),),
            max_time_min=600.0,
            snapshot_interval_min=60.0,
            weather_steps=weather,
            fire_stopping_precipitation_mm=12.7,
        ),
    )
    assert stopped.burned_area_ha < free.burned_area_ha


def test_rain_stopping_window_is_rolling() -> None:
    grid = make_grid(rows=21, cols=21)
    weather = tuple(
        WeatherStep(
            start_min=float(index * 60),
            wind_kmh=0.0,
            wind_direction_deg=0.0,
            ffmc=90.0,
            bui=60.0,
            relative_humidity_percent=40.0,
            precipitation_mm=0.0,
        )
        for index in range(5)
    )
    weather = (
        *weather,
        WeatherStep(
            start_min=300.0,
            wind_kmh=0.0,
            wind_direction_deg=0.0,
            ffmc=90.0,
            bui=60.0,
            relative_humidity_percent=40.0,
            precipitation_mm=20.0,
        ),
    )
    stopped = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((10, 10),),
            max_time_min=600.0,
            snapshot_interval_min=60.0,
            weather_steps=weather,
            fire_stopping_precipitation_mm=12.7,
            fire_stopping_window_min=120.0,
        ),
    )
    assert stopped.burned_area_ha > 0.0
