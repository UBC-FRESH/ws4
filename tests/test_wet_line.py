"""Tests for the P206 temporary wet-line pilot."""

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


def test_wet_line_pilot_writes_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module: Any = importlib.import_module("run_wet_line_2003_96")
    output = tmp_path / "wet.json"
    csv_path = tmp_path / "wet.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_wet_line_2003_96.py",
            "--ws4-root",
            str(ROOT),
            "--fixture",
            str(FIXTURES / "cfsds_2009_147"),
            "--wet-until",
            "0",
            "--output",
            str(output),
            "--csv",
            str(csv_path),
        ],
    )
    module.main()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["barrier"]["wet_until_min"] == [0.0]
    assert len(payload["rows"]) == 5
    assert csv_path.exists()


def test_wet_artifact_shows_weather_sensitive_containment() -> None:
    payload = json.loads((ROOT / "notes/reports/p206-wet-line.json").read_text(encoding="utf-8"))
    at_16000 = {row["area_sim_ha"] for row in payload["rows"] if row["wet_until_min"] == 16000.0}
    assert at_16000 == {98025.0, 158025.0}
