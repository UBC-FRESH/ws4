"""Tests for the durable tile-cache pre-warm."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from prewarm_tiles import (
    geometry_bounds,
    main,
    parse_bbox,
    parse_zooms,
    periods,
    prewarm,
)


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Create a tiny dataset, run, geometry, and cache directory."""
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "manifest.json").write_text('{"schema_version": "0.1"}', encoding="utf-8")
    runs = tmp_path / "runs"
    run = runs / "run1"
    run.mkdir(parents=True)
    (run / "summary.json").write_text('{"status": "ok"}', encoding="utf-8")
    (run / "schedule.csv").write_text("block_id,treatment,offset\n1,CC,0\n", encoding="utf-8")
    geometry = tmp_path / "geometry.geojson"
    geometry.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"block_id": 1},
                        "geometry": {"type": "Point", "coordinates": [0.5, 0.5]},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    cache = tmp_path / "cache"
    return dataset, runs, geometry, cache


def test_parse_zooms_accepts_ranges_and_lists() -> None:
    """A range and a list both become an ordered set of zoom levels."""
    assert parse_zooms("0-2") == (0, 1, 2)
    assert parse_zooms("2,0,2") == (2, 0)
    with pytest.raises(ValueError, match="reversed"):
        parse_zooms("3-1")
    with pytest.raises(ValueError, match="between"):
        parse_zooms("23")


def test_parse_bbox_requires_four_numbers() -> None:
    """The bbox is west,south,east,north."""
    assert parse_bbox("-130,50,-124,56") == (-130.0, 50.0, -124.0, 56.0)
    with pytest.raises(ValueError, match="bbox"):
        parse_bbox("1,2,3")


def test_geometry_bounds_reads_the_coordinates(tmp_path: Path) -> None:
    """The bounds are the min and max of the geometry coordinates."""
    path = tmp_path / "g.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "Feature",
                "properties": {"block_id": 7},
                "geometry": {"type": "Point", "coordinates": [1.0, 2.0]},
            }
        ),
        encoding="utf-8",
    )
    assert geometry_bounds(path) == (1.0, 2.0, 1.0, 2.0)


def test_periods_walk_the_horizon() -> None:
    """The default is the first year; a width produces period-end requests."""
    assert periods(1, 0) == [(0, None)]
    assert periods(10, 5) == [(4, 0), (9, 5)]


def test_prewarm_writes_durable_tiles(tmp_path: Path) -> None:
    """A pre-warm request writes the tile under the durable cache."""
    dataset, runs, geometry, cache = _fixture(tmp_path)
    report = prewarm(
        dataset=dataset,
        runs=runs,
        geometry=geometry,
        tile_cache=cache,
        bbox=(-1.0, -1.0, 1.0, 1.0),
        zooms=(0,),
        layers=("blocks",),
        run="run1",
        max_tiles=10,
        crs="EPSG:4326",
    )
    assert report["requested"] == 1
    assert report["failed"] == 0
    assert list(cache.rglob("*.mvt"))


def test_prewarm_rejects_an_unknown_layer(tmp_path: Path) -> None:
    """A layer outside the MVT set is named before any request."""
    dataset, runs, geometry, cache = _fixture(tmp_path)
    with pytest.raises(ValueError, match="unknown layer"):
        prewarm(
            dataset=dataset,
            runs=runs,
            geometry=geometry,
            tile_cache=cache,
            bbox=(0.0, 0.0, 1.0, 1.0),
            layers=("patches",),
        )


def test_main_writes_the_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI writes the report and exits zero when every tile answers."""
    dataset, runs, geometry, cache = _fixture(tmp_path)
    out = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prewarm_tiles.py",
            "--dataset",
            str(dataset),
            "--runs",
            str(runs),
            "--geometry",
            str(geometry),
            "--tile-cache",
            str(cache),
            "--bbox=-1,-1,1,1",
            "--zooms",
            "0",
            "--run",
            "run1",
            "--max-tiles",
            "1",
            "--out",
            str(out),
        ],
    )
    assert main() == 0
    assert json.loads(out.read_text(encoding="utf-8"))["requested"] == 1


def test_prewarm_writes_compare_tiles(tmp_path: Path) -> None:
    """The compare layer warms a tile for the named run pair."""
    dataset, runs, geometry, cache = _fixture(tmp_path)
    other = runs / "run2"
    other.mkdir()
    (other / "summary.json").write_text('{"status": "ok"}', encoding="utf-8")
    (other / "schedule.csv").write_text("block_id,treatment,offset\n1,CT,0\n", encoding="utf-8")
    report = prewarm(
        dataset=dataset,
        runs=runs,
        geometry=geometry,
        tile_cache=cache,
        bbox=(-1.0, -1.0, 1.0, 1.0),
        zooms=(0,),
        layers=("compare",),
        run="run1",
        compare_against="run2",
        max_tiles=10,
        crs="EPSG:4326",
    )
    assert report["requested"] == 1
    assert report["failed"] == 0
    tiles = list(cache.rglob("*.mvt"))
    assert len(tiles) == 1
    assert "compare-vs-run2" in str(tiles[0])
