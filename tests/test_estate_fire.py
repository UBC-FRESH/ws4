"""Tests for the calibrated estate fire handoff API."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from ws4.ecosystem.estate_fire import (
    EstateFireError,
    build_estate_fire_source,
    load_calibrated_regions,
    load_estate_grid,
)
from ws4.ecosystem.growth_fire import SurvivalIgnition
from ws4.fire.growth import FragmentSupport, GrowthConfig, WeatherStep


def _parameters(median: float) -> dict[str, float]:
    """Return a valid suppression parameter set."""
    return {
        "contained_fraction_median": median,
        "contained_fraction_sigma": 0.1,
        "escaped_fraction_median": 0.5,
        "escaped_fraction_sigma": 0.2,
        "escape_cap_ha": 1_000.0,
        "intercept": -2.0,
    }


def _retention_parameters(median: float) -> dict[str, float]:
    """Return a valid retention parameter set."""
    return {
        "contained_median_ha": median,
        "contained_sigma": 0.37,
        "contained_exponent": 0.4,
        "escaped_fraction_median": 0.5,
        "escaped_fraction_sigma": 0.2,
        "escape_cap_ha": 12_000.0,
        "intercept": -4.0,
    }


def _layer_arrays() -> dict[str, np.ndarray]:
    """Return a small layer stack."""
    fuel = np.empty((2, 2), dtype=object)
    fuel[:] = "C2"
    return {
        "fuel": fuel,
        "forest": np.ones((2, 2), dtype=bool),
        "water": np.zeros((2, 2), dtype=bool),
        "wet": np.zeros((2, 2), dtype=bool),
        "dem": np.ones((2, 2), dtype=float),
        "slope": np.ones((2, 2), dtype=float),
        "aspect": np.ones((2, 2), dtype=float),
        "crown": np.full((2, 2), 50.0),
        "conifer": np.full((2, 2), 100.0),
    }


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    """Write a layer manifest and calibration/tile manifests."""
    layer_path = tmp_path / "tile.npz"
    arrays = _layer_arrays()
    np.savez(
        layer_path,
        fuel=arrays["fuel"],
        forest=arrays["forest"],
        water=arrays["water"],
        wet=arrays["wet"],
        dem=arrays["dem"],
        slope=arrays["slope"],
        aspect=arrays["aspect"],
        crown=arrays["crown"],
        conifer=arrays["conifer"],
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "tiles": [
                    {
                        "tile_id": "tile",
                        "minx": 0.0,
                        "miny": 500.0,
                        "maxx": 500.0,
                        "maxy": 1_000.0,
                        "path": "tile.npz",
                    }
                ]
            }
        )
    )
    calibration = tmp_path / "calibration.json"
    calibration.write_text(json.dumps({"t01": {"parameters": _parameters(0.5)}}))
    tiles = tmp_path / "tiles.json"
    tiles.write_text(
        json.dumps(
            {
                "tiles": [
                    {
                        "id": "t01",
                        "minx": 0.0,
                        "miny": 500.0,
                        "maxx": 500.0,
                        "maxy": 1_000.0,
                    },
                    {
                        "id": "t24",
                        "minx": 0.0,
                        "miny": 0.0,
                        "maxx": 500.0,
                        "maxy": 500.0,
                    },
                ]
            }
        )
    )
    return manifest, calibration


def test_load_estate_grid_reads_tiles(tmp_path: Path) -> None:
    manifest, _calibration = _write_inputs(tmp_path)
    mask = np.ones((2, 2), dtype=bool)
    grid = load_estate_grid(
        manifest,
        rows=2,
        cols=2,
        origin_x=0.0,
        origin_y=1_000.0,
        cell_size_m=250.0,
        support_mask=mask,
    )
    assert grid.fuel_type_grid is not None
    assert grid.fuel_type_grid[0, 0] == "C2"
    assert grid.burnable is not None
    assert bool(grid.burnable.all())
    assert grid.rows == 2


def test_load_estate_grid_rejects_uncovered_support(tmp_path: Path) -> None:
    manifest, _calibration = _write_inputs(tmp_path)
    mask = np.ones((3, 2), dtype=bool)
    with pytest.raises(EstateFireError, match="not covered"):
        load_estate_grid(
            manifest,
            rows=3,
            cols=2,
            origin_x=0.0,
            origin_y=1_000.0,
            cell_size_m=250.0,
            support_mask=mask,
        )


def test_load_calibrated_regions_uses_median_fallback(tmp_path: Path) -> None:
    _manifest, calibration = _write_inputs(tmp_path)
    tiles = tmp_path / "tiles.json"
    configs, regions = load_calibrated_regions(
        calibration,
        tiles,
        rows=2,
        cols=2,
        origin_x=0.0,
        origin_y=1_000.0,
        cell_size_m=250.0,
    )
    assert configs[1].contained_fraction_median == pytest.approx(0.5)
    assert configs[2] == configs[0]
    assert regions[0, 0] == 1


def test_load_calibrated_regions_accepts_retention_schema(tmp_path: Path) -> None:
    """The public loader reads the calibrated retention map."""
    _manifest, calibration = _write_inputs(tmp_path)
    calibration.write_text(json.dumps({"t01": {"parameters": _retention_parameters(42.0)}}))
    tiles = tmp_path / "tiles.json"
    configs, _regions = load_calibrated_regions(
        calibration,
        tiles,
        rows=2,
        cols=2,
        origin_x=0.0,
        origin_y=1_000.0,
        cell_size_m=250.0,
    )

    assert configs[1].contained_median_ha == pytest.approx(42.0)
    assert configs[1].contained_fraction_sigma == pytest.approx(0.37)
    assert configs[1].contained_exponent == pytest.approx(0.4)


def test_load_estate_grid_resolves_archive_layer_directory(tmp_path: Path) -> None:
    """A full-layer manifest path can resolve through the archive ``layers`` directory."""
    manifest, _calibration = _write_inputs(tmp_path)
    layer = tmp_path / "tile.npz"
    archive_layers = tmp_path / "layers"
    archive_layers.mkdir()
    (archive_layers / "tile.npz").write_bytes(layer.read_bytes())
    payload = json.loads(manifest.read_text())
    payload["tiles"][0]["path"] = "data/tsa24-full-layers/tile.npz"
    manifest.write_text(json.dumps(payload))
    grid = load_estate_grid(
        manifest,
        rows=2,
        cols=2,
        origin_x=0.0,
        origin_y=1_000.0,
        cell_size_m=250.0,
        support_mask=np.ones((2, 2), dtype=bool),
    )

    assert grid.rows == 2
    assert grid.cols == 2


def test_build_estate_fire_source_returns_source_and_grid(tmp_path: Path) -> None:
    manifest, calibration = _write_inputs(tmp_path)
    tiles = tmp_path / "tiles.json"
    support = FragmentSupport(
        rows=2,
        cols=2,
        cell_index=np.array([0, 1, 2, 3], dtype=np.int64),
        fragment_id=np.array([1, 2, 3, 4], dtype=np.int64),
        weight=np.ones(4, dtype=float),
    )
    source, grid, regions = build_estate_fire_source(
        support,
        layer_manifest=manifest,
        calibration=calibration,
        tiles_manifest=tiles,
        origin_x=0.0,
        origin_y=1_000.0,
        cell_size_m=250.0,
        ignitions_by_year={
            0: [
                SurvivalIgnition(
                    cell=(0, 0),
                    active_days=0.1,
                    fwi=20.0,
                    bui=60.0,
                    wind_kmh=5.0,
                    active_hours_per_day=10.0,
                )
            ]
        },
        growth=GrowthConfig(
            ignition_cells=((0, 0),),
            max_time_min=10.0,
            weather_steps=(
                WeatherStep(
                    start_min=0.0,
                    wind_kmh=5.0,
                    wind_direction_deg=270.0,
                    ffmc=92.0,
                    bui=60.0,
                    relative_humidity_percent=30.0,
                    precipitation_mm=0.0,
                ),
            ),
        ),
        seed=1,
    )
    assert source.ignitions[0]
    assert grid.rows == 2
    assert regions[0, 0] == 1
