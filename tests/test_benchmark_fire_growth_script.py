"""Tests for the benchmark script's scenario builders and output path."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

module = importlib.import_module("benchmark_fire_growth")


def test_benchmark_scenario_builders() -> None:
    benchmark = module.benchmark_scenarios()
    ensemble = module.ensemble_scenarios()

    assert len(benchmark) == 20
    assert len(ensemble) == 54
    assert len({scenario.scenario_id for scenario in benchmark}) == 20
    assert len({scenario.scenario_id for scenario in ensemble}) == 54
    assert {scenario.fuel_type for scenario in benchmark} == {"C2", "C3", "C7", "M1", "S1"}
    assert {scenario.wind_kmh for scenario in benchmark} == {0.0, 10.0, 20.0, 30.0}


def test_error_summary_reports_mean_and_max() -> None:
    frame = pd.DataFrame(
        {
            "length_relative_error": [0.1, -0.2],
            "width_relative_error": [0.0, 0.1],
            "area_relative_error": [0.05, -0.15],
            "perimeter_relative_error": [0.2, 0.4],
        }
    )
    summary = module._error_summary(frame)

    assert summary["length_relative_error_mean_abs"] == 0.15000000000000002
    assert summary["length_relative_error_max_abs"] == 0.2
    assert summary["perimeter_relative_error_max_abs"] == 0.4


def test_main_writes_the_benchmark_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    frame = pd.DataFrame(
        {
            "scenario_id": ["s1"],
            "length_relative_error": [0.0],
            "width_relative_error": [0.0],
            "area_relative_error": [0.0],
            "perimeter_relative_error": [0.0],
        }
    )
    monkeypatch.setattr("ws4.fire.benchmark.run_growth_ensemble", lambda *args, **kwargs: frame)
    monkeypatch.setattr(
        "ws4.fire.benchmark.summarize_ensemble",
        lambda *args, **kwargs: {"count": 1, "p50": 0.0},
    )
    output = tmp_path / "benchmark.csv"
    summary = tmp_path / "summary.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark_fire_growth.py",
            "--output",
            str(output),
            "--summary",
            str(summary),
        ],
    )

    module.main()

    assert output.is_file()
    assert summary.is_file()
    assert "benchmark" in summary.read_text(encoding="utf-8")
    assert "benchmark" in capsys.readouterr().out
