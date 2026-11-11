"""Tests for the P172 fuel sensitivity diagnostic."""

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


def test_fuel_diagnostic_writes_per_cell_and_homogeneous(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The diagnostic writes per-cell and homogeneous rows."""
    module: Any = importlib.import_module("diagnose_fuel_sensitivity")
    output = tmp_path / "fuel.json"
    csv = tmp_path / "fuel.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "diagnose_fuel_sensitivity.py",
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
    assert payload["summary"]["case_count"] == 1
    assert payload["rows"][0]["per_cell_ratio"] > 2.0
    assert len(pd.read_csv(csv)) == 1
