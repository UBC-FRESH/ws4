"""Tests for the observed-fire contract and the Dogrib fixture."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest
from ws4.fire.observed import (
    OBSERVED_FIRE_VERSION,
    ObservedFireError,
    load_dogrib,
    read_ascii_grid,
    read_kml_rings,
)

FIXTURE = Path(__file__).parent / "fixtures" / "fire" / "dogrib"


def test_dogrib_fixture_loads_with_geometry_and_weather() -> None:
    fire = load_dogrib(FIXTURE)

    assert fire.fire_id == "RWF085"
    assert fire.version == OBSERVED_FIRE_VERSION
    assert fire.grid.ncols == 357
    assert fire.grid.nrows == 223
    assert fire.grid.cell_size_m == 100.0
    assert fire.grid.contains(*fire.ignition_xy)
    assert len(fire.weather) == 864
    assert len(fire.perimeters) == 2
    assert fire.perimeters[0].observed_at.isoformat() == "2001-10-16T13:00:00"
    assert fire.perimeters[1].observed_at.isoformat() == "2001-10-17T11:52:00"
    assert fire.perimeters[0].area_ha == pytest.approx(935.1, rel=0.02)
    assert fire.perimeters[1].area_ha == pytest.approx(10223.3, rel=0.02)
    assert fire.perimeters[1].to_dict()["polygons"] == 25
    assert fire.event_start < fire.event_end


def test_fuel_lookup_maps_fbp_and_non_fuel() -> None:
    fire = load_dogrib(FIXTURE)
    fuel = fire.fuel_type_grid()

    assert fuel.shape == fire.fuel_codes.shape
    assert fire.fuel_type_at(0, 12) == "O-1a/O-1b"
    assert fire.fuel_type_at(0, 0) is None
    assert {value for value in fuel.ravel() if value is not None} <= {
        "C-1",
        "C-2",
        "C-3",
        "C-4",
        "C-7",
        "D-1/D-2",
        "O-1a/O-1b",
        "M-1/M-2 (40 PC)",
        "M-1/M-2 (50 PC)",
        "M-1/M-2 (60 PC)",
    }


def test_weather_window_is_typed_and_closed() -> None:
    fire = load_dogrib(FIXTURE)
    window = fire.weather_between(fire.event_start, fire.event_end)

    assert len(window) == 23
    assert list(window.columns) == [
        "local_time",
        "temperature_c",
        "relative_humidity_percent",
        "wind_direction_deg",
        "wind_speed_kmh",
        "precipitation_mm",
    ]
    assert window["local_time"].is_monotonic_increasing


def test_summary_is_json_serializable() -> None:
    fire = load_dogrib(FIXTURE)
    payload = fire.to_dict()

    encoded = json.dumps(payload, sort_keys=True)
    assert OBSERVED_FIRE_VERSION in encoded
    perimeters = payload["perimeters"]
    grid = payload["grid"]
    assert isinstance(perimeters, list)
    assert isinstance(perimeters[1], dict)
    assert isinstance(grid, dict)
    assert perimeters[1]["area_ha"] > 10_000.0
    assert grid["cell_size_m"] == 100.0


def test_ascii_grid_rejects_malformed_shape(tmp_path: Path) -> None:
    path = tmp_path / "bad.asc"
    path.write_text(
        "NCOLS 2\nNROWS 2\nXLLCORNER 0\nYLLCORNER 0\nCELLSIZE 10\nNODATA_value -9999\n1 2\n",
        encoding="utf-8",
    )
    with pytest.raises(ObservedFireError, match="shape"):
        read_ascii_grid(path)


def test_kml_ring_reader_requires_exterior_polygons(tmp_path: Path) -> None:
    path = tmp_path / "empty.kml"
    path.write_text("<kml><Document/></kml>", encoding="utf-8")
    with pytest.raises(ObservedFireError, match="exterior"):
        read_kml_rings(path)


def test_loader_rejects_a_missing_fuel_file(tmp_path: Path) -> None:
    broken = tmp_path / "dogrib"
    shutil.copytree(FIXTURE, broken)
    (broken / "fbp_fuel_type.asc").unlink()
    with pytest.raises(ObservedFireError, match="ASCII grid"):
        load_dogrib(broken)


def test_loader_rejects_an_unknown_fuel_code(tmp_path: Path) -> None:
    broken = tmp_path / "dogrib"
    shutil.copytree(FIXTURE, broken)
    lookup = pd.read_csv(broken / "fbp_lookup_table.csv")
    lookup = lookup[lookup["grid_value"] != 1]
    lookup.to_csv(broken / "fbp_lookup_table.csv", index=False)
    with pytest.raises(ObservedFireError, match="unknown codes"):
        load_dogrib(broken)


def test_loader_rejects_a_weather_gap(tmp_path: Path) -> None:
    broken = tmp_path / "dogrib"
    shutil.copytree(FIXTURE, broken)
    weather = pd.read_csv(broken / "weather_B3_hourly_20010925to1030.csv")
    weather = weather[weather["HOURLY"] != "16/10/2001"]
    weather.to_csv(broken / "weather_B3_hourly_20010925to1030.csv", index=False)
    with pytest.raises(ObservedFireError, match="gap"):
        load_dogrib(broken)
