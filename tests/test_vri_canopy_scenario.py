"""Tests for the VRI canopy-only treatment scenario."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _feature() -> dict[str, object]:
    return {
        "type": "Feature",
        "properties": {
            "FEATURE_ID": 1,
            "BCLCS_LEVEL_1": "V",
            "CROWN_CLOSURE": 70,
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1000, 0], [1000, 1000], [0, 1000], [0, 0]]],
        },
    }


def test_features_and_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module: Any = importlib.import_module("vri_canopy_scenario")
    features = module._features({"features": [_feature()]})
    assert len(features) == 1
    with pytest.raises(ValueError, match="no complete"):
        module._features({"features": []})
    source = tmp_path / "vri.geojson"
    source.write_text(json.dumps({"type": "FeatureCollection", "features": [_feature()]}))
    output = tmp_path / "scenario.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vri_canopy_scenario.py",
            "--input",
            str(source),
            "--treatment",
            "thin-burn",
            "--output",
            str(output),
        ],
    )
    module.main()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["grid"]["fuel_type"] == "C2"
    assert payload["area_difference_ha"] == 0.0
    assert payload["control"]["burned_area_ha"] > 0.0
