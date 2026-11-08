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
    EffectiveWind,
    GrowthConfig,
    SiteGrid,
    effective_wind,
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
