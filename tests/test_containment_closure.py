"""Integration test for the P203 containment-closure pilot runner."""

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


def test_closure_pilot_writes_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pilot records closure time, weather member and geometry."""
    module: Any = importlib.import_module("run_containment_closure_2003_96")
    output = tmp_path / "closure.json"
    csv_path = tmp_path / "closure.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_containment_closure_2003_96.py",
            "--ws4-root",
            str(ROOT),
            "--fixture",
            str(FIXTURES / "cfsds_2009_147"),
            "--closures",
            "0",
            "--output",
            str(output),
            "--csv",
            str(csv_path),
        ],
    )
    module.main()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["barrier"]["closures_min"] == [0.0]
    assert len(payload["rows"]) == 5
    assert "east_of_barrier_burned_cells" in payload["rows"][0]
    assert csv_path.exists()
