"""Tests for the P208 drop-depth pilot."""

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


def test_ellipse_coverage_and_depth_grid() -> None:
    module: Any = importlib.import_module("run_drop_depth_2003_96")
    coverage = module.ellipse_coverage(
        center_x=0.0,
        center_y=0.0,
        length_m=100.0,
        width_m=50.0,
        cell_x=0.0,
        cell_y=0.0,
        cell_size_m=100.0,
    )
    assert 0.3 < coverage < 0.5
    depth = module.build_depth_grid(
        rows=3,
        cols=3,
        xll=0.0,
        yll=0.0,
        cell_size_m=100.0,
        gap_cells=[(1, 1)],
        drops_per_cell=1,
        volume_l=6000.0,
        length_m=100.0,
        width_m=50.0,
    )
    assert depth[1, 1] > 0.0
    assert depth.sum() == pytest.approx(depth[1, 1])


def test_drop_depth_pilot_writes_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module: Any = importlib.import_module("run_drop_depth_2003_96")
    output = tmp_path / "drop.json"
    csv_path = tmp_path / "drop.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_drop_depth_2003_96.py",
            "--ws4-root",
            str(ROOT),
            "--fixture",
            str(FIXTURES / "cfsds_2009_147"),
            "--drop-times",
            "0",
            "--output",
            str(output),
            "--csv",
            str(csv_path),
        ],
    )
    module.main()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["barrier"]["drop_times_min"] == [0.0]
    assert len(payload["rows"]) == 5
    assert csv_path.exists()
