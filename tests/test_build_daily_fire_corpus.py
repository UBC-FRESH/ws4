"""Tests for the daily corpus manifest script."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from ws4.fire.daily_corpus import DailyCase

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _case(case_id: str, year: int, ecozone: int, area: float) -> DailyCase:
    """Build one fake daily case."""
    return DailyCase(
        case_id=case_id,
        year=year,
        days=3,
        final_area_ha=area,
        raster_area_ha=area,
        area_relative_error=0.0,
        ecozone=ecozone,
        lon=-115.0,
        lat=60.0,
        fuel_code=1,
        elevation_m=300.0,
        status="ready",
    )


def test_main_writes_daily_manifest_and_csv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The script writes JSON, CSV, and the gate result."""
    module: Any = importlib.import_module("build_daily_fire_corpus")
    cases = (
        _case("2023_1", 2023, 14, 1000.0),
        _case("2003_1", 2003, 9, 500.0),
    )
    monkeypatch.setattr(
        "ws4.fire.daily_corpus.build_daily_corpus",
        lambda *args, **kwargs: (cases, 5, 1),
    )
    output = tmp_path / "daily.json"
    csv = tmp_path / "daily.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_daily_fire_corpus.py",
            "--data-root",
            str(tmp_path),
            "--output",
            str(output),
            "--csv",
            str(csv),
        ],
    )

    module.main()

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["case_count"] == 2
    assert data["candidate_count"] == 5
    assert data["rejected_count"] == 1
    frame = pd.read_csv(csv)
    assert list(frame["case_id"]) == ["2023_1", "2003_1"]
