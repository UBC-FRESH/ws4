"""Tests for the P164.8 potential-sample builder."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest
from ws4.fire.fwi import DailyWeather, fwi_sequence

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fire_regime" / "build_potential.py"
_SPEC = importlib.util.spec_from_file_location("build_potential", _SCRIPT)
assert _SPEC is not None
assert _SPEC.loader is not None
module = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = module
_SPEC.loader.exec_module(module)


def _daily() -> list[DailyWeather]:
    """Return a short deterministic weather series."""
    return [
        DailyWeather(
            year=2023,
            month=5,
            day=1 + index,
            temperature_c=25.0,
            relative_humidity_percent=30.0,
            wind_kmh=8.0,
            precipitation_mm=0.0,
            latitude_deg=54.0,
        )
        for index in range(20)
    ]


def test_tile_manifest_has_the_fixed_split() -> None:
    split, tiles = module.load_tiles(Path("scripts/fire_regime/tiles.json"))

    assert len(tiles) == 24
    assert len(split["train"]) == 12
    assert len(split["validation"]) == 12


def test_start_selection_is_deterministic_and_in_season() -> None:
    daily = _daily()
    states = fwi_sequence(daily)

    first = module.select_start_indices(daily, states, count=10, seed=4)
    second = module.select_start_indices(daily, states, count=10, seed=4)

    assert first == second
    assert len(first) == 10
    assert all(5 <= daily[index].month <= 9 for index in first)


def test_build_case_runs_a_potential_fire(tmp_path: Path) -> None:
    layers = tmp_path / "tile.npz"
    fuel = np.empty((5, 5), dtype=object)
    fuel[:] = "C2"
    np.savez_compressed(
        layers,
        fuel=fuel,
        forest=np.ones((5, 5), dtype=bool),
        wet=np.zeros((5, 5), dtype=bool),
        crown=np.full((5, 5), 50.0),
        conifer=np.full((5, 5), 100.0),
        dem=np.zeros((5, 5)),
        slope=np.zeros((5, 5)),
        aspect=np.zeros((5, 5)),
    )
    daily = tuple(_daily())
    states = fwi_sequence(list(daily))
    tile = module.Tile("test", 0, 0, 1000, 1000, "tile.npz")

    record = module.build_case(
        tile,
        tmp_path,
        daily,
        tuple(300.0 for _ in daily),
        states,
        0,
        seed=3,
    )

    assert record["tile"] == "test"
    assert record["potential_ha"] > 0.0
    assert record["active_days"] >= 0.5


def test_start_selection_rejects_no_season() -> None:
    daily = [
        DailyWeather(
            year=2023,
            month=1,
            day=1,
            temperature_c=0.0,
            relative_humidity_percent=80.0,
            wind_kmh=1.0,
            precipitation_mm=0.0,
        )
        for _ in range(10)
    ]
    with pytest.raises(ValueError, match="fire-season"):
        module.select_start_indices(daily, fwi_sequence(daily), count=1, seed=1)
