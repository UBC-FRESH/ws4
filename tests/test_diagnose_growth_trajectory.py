"""Tests for the P169 trajectory diagnostic script."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fire"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def test_diagnostic_writes_trajectory_and_radius(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The diagnostic writes daily ratios and radius sensitivity."""
    module: Any = importlib.import_module("diagnose_growth_trajectory")
    output = tmp_path / "trajectory.json"
    csv = tmp_path / "trajectory.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "diagnose_growth_trajectory.py",
            "--fixtures",
            str(FIXTURES / "cfsds_2009_147"),
            "--output",
            str(output),
            "--csv",
            str(csv),
        ],
    )

    module.main()

    payload = json.loads(output.read_text(encoding="utf-8"))
    row = payload["rows"][0]
    assert row["case"] == "2009_147"
    assert row["area_ratio_day1"] < 2.0
    assert row["area_ratio_r2"] > 2.0
    assert len(row["daily_ratios"]) == 2
    assert len(pd.read_csv(csv)) == 1
