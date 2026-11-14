"""Tests for the P178 free-burn ensemble runner."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fire"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def test_weather_member_scales_wind_offsets_rh_and_preserves_source() -> None:
    """Weather perturbations are applied without mutating the source fire."""
    module: Any = importlib.import_module("run_freeburn_ensemble")
    from ws4.fire.observed import load_cfsds_reanalysis_case

    fire = load_cfsds_reanalysis_case(FIXTURES / "cfsds_2009_147")
    original = fire.weather.copy(deep=True)
    perturbed = module._weather_member(fire, wind_scale=1.2, rh_offset=-10.0)
    assert np.allclose(
        perturbed.weather["wind_speed_kmh"],
        original["wind_speed_kmh"] * 1.2,
    )
    assert np.allclose(
        perturbed.weather["relative_humidity_percent"],
        (original["relative_humidity_percent"] - 10.0).clip(1.0, 100.0),
    )
    assert perturbed.weather["relative_humidity_percent"].max() <= 100.0
    assert fire.weather.equals(original)


def test_diagnostic_burning_conditions_are_fixed_and_labelled() -> None:
    """The diagnostic gate has explicit thresholds and provenance."""
    module: Any = importlib.import_module("run_freeburn_ensemble")
    gate = module.diagnostic_burning_conditions()
    assert gate.isi_gt == 8.0
    assert gate.wind_gt_kmh == 5.0
    assert gate.relative_humidity_lt_percent == 50.0
    assert "not calibrated" in gate.source


def test_time_to_observed_area_uses_first_matching_snapshot() -> None:
    """The timing endpoint uses the first snapshot at or above observed area."""
    module: Any = importlib.import_module("run_freeburn_ensemble")
    snapshots = (
        SimpleNamespace(time_min=0.0, area_ha=10.0),
        SimpleNamespace(time_min=60.0, area_ha=25.0),
        SimpleNamespace(time_min=120.0, area_ha=40.0),
    )
    assert module._time_to_observed_area(snapshots, 20.0) == 60.0
    assert module._time_to_observed_area(snapshots, 50.0) is None
    assert module._time_to_observed_area(snapshots, 0.0) is None


def test_summary_reports_overall_and_per_case_spread() -> None:
    """The summary includes per-case and timing spread."""
    module: Any = importlib.import_module("run_freeburn_ensemble")
    rows = [
        {
            "case": "A",
            "area_bias": 1.0,
            "iou": 0.2,
            "time_to_observed_area_min": 10.0,
        },
        {
            "case": "A",
            "area_bias": 3.0,
            "iou": 0.4,
            "time_to_observed_area_min": 20.0,
        },
        {
            "case": "B",
            "area_bias": 2.0,
            "iou": 0.3,
            "time_to_observed_area_min": None,
        },
    ]
    summary = module._summary(rows)
    assert summary["run_count"] == 3
    assert summary["case_count"] == 2
    assert summary["time_to_observed_area_min"]["range"] == 10.0
    assert summary["per_case"]["A"]["area_bias"]["range"] == 2.0
    assert summary["per_case"]["A"]["iou"]["range"] == pytest.approx(0.2)
    assert summary["per_case"]["A"]["time_to_observed_area_min"]["range"] == 10.0
    assert summary["per_case"]["B"]["time_to_observed_area_min"] is None


def test_freeburn_ensemble_writes_members(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runner records five weather members for one case."""
    module: Any = importlib.import_module("run_freeburn_ensemble")
    output = tmp_path / "ensemble.json"
    csv = tmp_path / "ensemble.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_freeburn_ensemble.py",
            "--fixtures",
            str(FIXTURES / "cfsds_2009_147"),
            "--output",
            str(output),
            "--csv",
            str(csv),
            "--burning-conditions",
        ],
    )

    module.main()

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["summary"]["run_count"] == 5
    assert len(payload["rows"]) == 5
    assert len({row["member"] for row in payload["rows"]}) == 5
    assert all("time_to_observed_area_min" in row for row in payload["rows"])
    assert payload["burning_conditions"]["isi_gt"] == 8.0
    assert payload["burning_conditions"]["wind_gt_kmh"] == 5.0
    assert payload["burning_conditions"]["relative_humidity_lt_percent"] == 50.0
    assert payload["summary"]["per_case"]
    assert len(pd.read_csv(csv)) == 5
