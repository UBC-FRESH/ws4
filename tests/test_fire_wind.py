"""Tests for the WindNinja wind-grid inputs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from ws4.fire.fuel import FireFuelError
from ws4.fire.observed import ObservedGrid
from ws4.fire.wind import (
    WindNinjaGrid,
    angular_distance,
    grid_cell_for_xy,
    load_windninja_directory,
    nearest_wind_direction,
    read_windninja_pair,
    wind_grid_at,
)


def _ascii(values: list[float], *, ncols: int = 2, nrows: int = 2) -> str:
    """Return a tiny ESRI ASCII grid."""
    return (
        f"ncols {ncols}\n"
        f"nrows {nrows}\n"
        "xllcorner 0\n"
        "yllcorner 0\n"
        "cellsize 10\n"
        "NODATA_value -9999\n"
        + "\n".join(
            " ".join(str(value) for value in values[index : index + ncols])
            for index in range(0, len(values), ncols)
        )
        + "\n"
    )


def _write_pair(
    root: Path, direction: int, *, angle: str | None = None, speed: str | None = None
) -> None:
    """Write one synthetic pair for a direction."""
    (root / f"windninja_{direction}_30_100m_ang.asc").write_text(
        angle if angle is not None else _ascii([90.0, 90.0, 90.0, 90.0]),
        encoding="utf-8",
    )
    (root / f"windninja_{direction}_30_100m_vel.asc").write_text(
        speed if speed is not None else _ascii([10.0, 10.0, 10.0, 10.0]),
        encoding="utf-8",
    )


def test_read_windninja_pair_validates_and_serializes(tmp_path: Path) -> None:
    _write_pair(tmp_path, 270)
    grid = read_windninja_pair(
        tmp_path / "windninja_270_30_100m_ang.asc",
        tmp_path / "windninja_270_30_100m_vel.asc",
        direction_deg=270,
        method="conservation_of_mass",
        source="test archive",
        crs="local",
    )

    assert grid.direction_deg == 270
    assert grid.geometry.ncols == 2
    assert grid.speed_kmh[0, 0] == pytest.approx(10.0)
    assert grid.to_dict()["method"] == "conservation_of_mass"


def test_mismatched_wind_grid_shape_fails(tmp_path: Path) -> None:
    _write_pair(
        tmp_path,
        270,
        speed=_ascii([10.0, 10.0, 10.0, 10.0], ncols=2, nrows=2),
    )
    (tmp_path / "windninja_270_30_100m_vel.asc").write_text(
        _ascii([10.0] * 6, ncols=2, nrows=3),
        encoding="utf-8",
    )

    with pytest.raises(FireFuelError, match="share one geometry"):
        read_windninja_pair(
            tmp_path / "windninja_270_30_100m_ang.asc",
            tmp_path / "windninja_270_30_100m_vel.asc",
            direction_deg=270,
            method="conservation_of_mass",
            source="test archive",
            crs="local",
        )


def test_directory_load_requires_both_members(tmp_path: Path) -> None:
    _write_pair(tmp_path, 270)
    (tmp_path / "windninja_360_30_100m_ang.asc").write_text(
        _ascii([0.0, 0.0, 0.0, 0.0]),
        encoding="utf-8",
    )

    with pytest.raises(FireFuelError, match="missing a pair"):
        load_windninja_directory(
            tmp_path,
            method="conservation_of_mass",
            source="test archive",
            crs="local",
        )


def test_nearest_direction_uses_circular_distance() -> None:
    assert nearest_wind_direction((90, 240, 270, 315, 360), 0.0) == 360
    assert nearest_wind_direction((90, 240, 270, 315, 360), 80.0) == 90
    assert angular_distance(350.0, 10.0) == pytest.approx(20.0)
    with pytest.raises(FireFuelError, match="at least one"):
        nearest_wind_direction((), 0.0)


def test_wind_grid_at_selects_the_nearest_grid_and_cell(tmp_path: Path) -> None:
    _write_pair(tmp_path, 90)
    _write_pair(tmp_path, 270)
    grids = load_windninja_directory(
        tmp_path,
        method="conservation_of_mass",
        source="test archive",
        crs="local",
    )

    speed, direction = wind_grid_at(grids, row=0, col=0, direction_deg=260.0)

    assert speed == pytest.approx(10.0)
    assert direction == pytest.approx(90.0)


def test_grid_cell_for_xy_uses_north_first_rows() -> None:
    geometry = ObservedGrid(2, 2, 0.0, 0.0, 10.0, -9999.0, "local")

    assert grid_cell_for_xy(geometry, 5.0, 15.0) == (0, 0)
    assert grid_cell_for_xy(geometry, 5.0, 5.0) == (1, 0)
    with pytest.raises(FireFuelError, match="outside"):
        grid_cell_for_xy(geometry, -1.0, 5.0)


def test_wind_grid_rejects_bad_values(tmp_path: Path) -> None:
    _write_pair(tmp_path, 270, angle=_ascii([400.0, 0.0, 0.0, 0.0]))
    with pytest.raises(FireFuelError, match="angles"):
        read_windninja_pair(
            tmp_path / "windninja_270_30_100m_ang.asc",
            tmp_path / "windninja_270_30_100m_vel.asc",
            direction_deg=270,
            method="conservation_of_mass",
            source="test archive",
            crs="local",
        )
    with pytest.raises(FireFuelError, match="non-empty"):
        WindNinjaGrid(
            direction_deg=270,
            angle_deg=np.zeros((1, 1)),
            speed_kmh=np.ones((1, 1)),
            geometry=ObservedGrid(1, 1, 0.0, 0.0, 10.0, -9999.0, "local"),
            method="",
            source="test",
        )
