"""Tests for the P229 Alberta waterbody screen."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from pyproj import Transformer

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _square(lon: float, lat: float, half: float, object_id: int) -> dict[str, Any]:
    ring = [
        [lon - half, lat - half],
        [lon + half, lat - half],
        [lon + half, lat + half],
        [lon - half, lat + half],
        [lon - half, lat - half],
    ]
    return {
        "attributes": {
            "OBJECTID": object_id,
            "FEATURE_TYPE": "LAKE-PER",
            "NAME": f"lake-{object_id}",
        },
        "geometry": {"rings": [ring]},
    }


def _gap_lon_lat() -> tuple[float, float]:
    transformer = Transformer.from_crs(32611, 4326, always_xy=True)
    return transformer.transform(636250.0, 6572250.0)


def test_screen_filters_area_and_orders_by_distance() -> None:
    module: Any = importlib.import_module("alberta_water_sources")
    lon, lat = _gap_lon_lat()
    features = [
        _square(lon, lat, 0.0005, 1),
        _square(lon + 0.002, lat, 0.002, 2),
        _square(lon + 0.02, lat, 0.002, 3),
    ]
    sources = module.screen_waterbodies(
        features,
        gap_x=636250.0,
        gap_y=6572250.0,
        min_area_ha=1.0,
    )
    assert [source.object_id for source in sources] == [2, 3]
    assert sources[0].area_ha > 1.0
    assert sources[0].distance_km < sources[1].distance_km
    assert sources[0].name == "lake-2"


def test_load_features_and_nearest_thresholds(tmp_path: Path) -> None:
    module: Any = importlib.import_module("alberta_water_sources")
    payload = {"features": [_square(-114.61, 59.27, 0.002, 1)]}
    path = tmp_path / "features.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    features = module.load_features(path)
    assert len(features) == 1
    sources = module.screen_waterbodies(
        features,
        gap_x=636250.0,
        gap_y=6572250.0,
        min_area_ha=0.1,
    )
    nearest = module.nearest_by_min_area(sources, minima_ha=(0.1, 1000.0))
    assert nearest["0.1_ha"]["object_id"] == 1
    assert nearest["1000_ha"] is None


def test_invalid_inputs(tmp_path: Path) -> None:
    module: Any = importlib.import_module("alberta_water_sources")
    empty = tmp_path / "empty.json"
    empty.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="no feature list"):
        module.load_features(empty)
    with pytest.raises(ValueError, match="no polygon rings"):
        module.screen_waterbodies(
            [{"geometry": {"type": "Polygon"}}],
            gap_x=0.0,
            gap_y=0.0,
        )


def test_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module: Any = importlib.import_module("alberta_water_sources")
    lon, lat = _gap_lon_lat()
    features = tmp_path / "features.json"
    features.write_text(
        json.dumps({"features": [_square(lon, lat, 0.002, 7)]}),
        encoding="utf-8",
    )
    output = tmp_path / "screen.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "alberta_water_sources.py",
            "--features",
            str(features),
            "--gap-x",
            "636250",
            "--gap-y",
            "6572250",
            "--min-area-ha",
            "0.1",
            "--output",
            str(output),
        ],
    )
    module.main()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["candidate_count"] == 1
    assert payload["sources"][0]["object_id"] == 7
    assert payload["nearest_by_min_area"]["1_ha"]["object_id"] == 7
