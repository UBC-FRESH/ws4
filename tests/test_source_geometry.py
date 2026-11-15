"""Tests for the P232 source-distance and drawdown check."""

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


def test_travel_budget() -> None:
    module: Any = importlib.import_module("source_geometry")
    budget = module.travel_budget_min(
        cycle_min=4.25,
        payload_l=6000.0,
        refill_l_min=4235.294,
    )
    assert budget == pytest.approx(2.833333, rel=1e-5)
    with pytest.raises(ValueError, match="no travel budget"):
        module.travel_budget_min(
            cycle_min=1.0,
            payload_l=6000.0,
            refill_l_min=4235.294,
        )


def test_evaluate_sources() -> None:
    module: Any = importlib.import_module("source_geometry")
    sources = [
        {
            "object_id": 1,
            "feature_type": "LAKE-PER",
            "name": None,
            "area_ha": 3.29,
            "distance_km": 0.38,
        },
        {
            "object_id": 2,
            "feature_type": "LAKE-PER",
            "name": "named",
            "area_ha": 18.45,
            "distance_km": 1.188,
        },
    ]
    metrics = module.evaluate_sources(sources, volume_l=480_000.0, budget_min=2.833333)
    assert [metric.object_id for metric in metrics] == [1, 2]
    assert metrics[0].drawdown_mm == pytest.approx(14.59, rel=1e-3)
    assert metrics[1].drawdown_mm == pytest.approx(2.60, rel=1e-2)
    assert metrics[1].required_speed_kmh == pytest.approx(50.3, rel=1e-2)
    with pytest.raises(ValueError, match="area must be positive"):
        module.evaluate_sources(
            [{"object_id": 3, "feature_type": "LAKE", "area_ha": 0.0, "distance_km": 1.0}],
            volume_l=480_000.0,
            budget_min=2.833333,
        )


def test_load_candidates_deduplicates(tmp_path: Path) -> None:
    module: Any = importlib.import_module("source_geometry")
    first = {
        "object_id": 2,
        "feature_type": "LAKE-PER",
        "name": None,
        "area_ha": 18.45,
        "distance_km": 1.188,
    }
    payload = {"nearest_by_min_area": {"1_ha": first, "5_ha": first, "100_ha": None}}
    path = tmp_path / "screen.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert module.load_candidates(path) == [first]
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="nearest_by_min_area"):
        module.load_candidates(invalid)


def test_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module: Any = importlib.import_module("source_geometry")
    source = {
        "object_id": 4,
        "feature_type": "LAKE-PER",
        "name": None,
        "area_ha": 18.45,
        "distance_km": 1.188,
    }
    sources = tmp_path / "screen.json"
    sources.write_text(
        json.dumps({"nearest_by_min_area": {"5_ha": source}}),
        encoding="utf-8",
    )
    output = tmp_path / "geometry.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "source_geometry.py",
            "--sources",
            str(sources),
            "--output",
            str(output),
        ],
    )
    module.main()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["parameters"]["travel_budget_min"] == pytest.approx(2.833333, rel=1e-5)
    assert payload["sources"][0]["object_id"] == 4
