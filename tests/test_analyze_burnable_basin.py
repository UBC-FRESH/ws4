"""Tests for the P176 burnable-basin diagnostic."""

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


def test_basin_diagnostic_writes_fractions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The diagnostic writes basin, observed, and simulated fractions."""
    module: Any = importlib.import_module("analyze_burnable_basin")
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps({"cases": [{"case": "2009_147", "area_sim_ha": 7000.0}]}),
        encoding="utf-8",
    )
    output = tmp_path / "basin.json"
    csv = tmp_path / "basin.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "analyze_burnable_basin.py",
            "--fixtures",
            str(FIXTURES / "cfsds_2009_147"),
            "--reports",
            str(report),
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
    assert row["sim_burnable"] > 0.9
    assert row["observed_burnable"] < 0.2
    assert len(pd.read_csv(csv)) == 1
