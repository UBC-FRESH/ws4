"""Integration test for the P204 rain-stopping pilot runner."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FIXTURES = ROOT / "tests" / "fixtures" / "fire"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def test_rain_pilot_writes_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The rain pilot records the criterion and five weather members."""
    module: Any = importlib.import_module("run_rain_stopping_2003_96")
    output = tmp_path / "rain.json"
    csv_path = tmp_path / "rain.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_rain_stopping_2003_96.py",
            "--ws4-root",
            str(ROOT),
            "--fixture",
            str(FIXTURES / "cfsds_2009_147"),
            "--output",
            str(output),
            "--csv",
            str(csv_path),
        ],
    )
    module.main()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["criterion"].startswith("Latham and Rothermel")
    assert len(payload["rows"]) == 5
    assert csv_path.exists()


def test_rain_artifact_shows_weather_sensitive_final_area() -> None:
    payload = json.loads(
        (ROOT / "notes/reports/p204-rain-stopping-2023-366.json").read_text(encoding="utf-8")
    )
    areas = {row["area_sim_ha"] for row in payload["rows"]}
    assert len(areas) > 1
    assert max(areas) < 1_149_275.0
