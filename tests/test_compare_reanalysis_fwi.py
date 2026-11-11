"""Tests for the P170 FWI consistency diagnostic."""

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


def test_fwi_diagnostic_writes_daily_deltas(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The diagnostic writes daily and summary FWI deltas."""
    module: Any = importlib.import_module("compare_reanalysis_fwi")
    output = tmp_path / "fwi.json"
    csv = tmp_path / "fwi.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compare_reanalysis_fwi.py",
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
    assert payload["summary"]["day_count"] == 2
    assert len(payload["rows"]) == 2
    assert "ffmc_delta" in payload["rows"][0]
    assert len(pd.read_csv(csv)) == 2
