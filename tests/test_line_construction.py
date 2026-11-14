"""Tests for the P205 line-construction pilot."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FIXTURES = ROOT / "tests" / "fixtures" / "fire"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def test_construction_schedule_uses_distance_and_rate() -> None:
    module: Any = importlib.import_module("run_line_construction_2003_96")
    closure = module.build_construction_schedule(
        rows=4,
        cols=5,
        barrier_col=2,
        cell_size_m=100.0,
        rate_m_h=60.0,
    )
    assert closure[0, 2] == 0.0
    assert closure[1, 2] == pytest.approx(100.0)
    assert closure[3, 2] == pytest.approx(300.0)
    assert np.isinf(closure[:, 1]).all()


def test_construction_pilot_writes_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module: Any = importlib.import_module("run_line_construction_2003_96")
    output = tmp_path / "line.json"
    csv_path = tmp_path / "line.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_line_construction_2003_96.py",
            "--ws4-root",
            str(ROOT),
            "--fixture",
            str(FIXTURES / "cfsds_2009_147"),
            "--rates",
            "20",
            "--output",
            str(output),
            "--csv",
            str(csv_path),
        ],
    )
    module.main()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["barrier"]["rates_m_h"] == [20.0]
    assert len(payload["rows"]) == 5
    assert csv_path.exists()


def test_rate_artifact_shows_construction_threshold() -> None:
    payload = json.loads(
        (ROOT / "notes/reports/p205-line-construction.json").read_text(encoding="utf-8")
    )
    areas = {float(row["rate_m_h"]): float(row["area_sim_ha"]) for row in payload["rows"]}
    assert areas[80.0] > areas[200.0]
    assert areas[200.0] == areas[400.0] == 98025.0
