"""Tests for the P161 Hay River calibration script's wiring."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest
from ws4.fire.calibration import CalibrationParameters
from ws4.fire.comparison import PerimeterMetrics

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

module = importlib.import_module("benchmark_hay_river_calibration")


class FakeCase:
    """A minimal case with the fields the script reads."""

    def __init__(self, scenario: str, area: float = 120.0) -> None:
        """Build one fake case."""
        self.scenario = scenario
        self.metrics = PerimeterMetrics(
            area_sim_ha=area,
            area_obs_ha=100.0,
            area_bias=(area - 100.0) / 100.0,
            perimeter_sim_m=120.0,
            perimeter_obs_m=100.0,
            perimeter_bias=0.2,
            centroid_distance_m=1000.0,
            iou=0.5,
            sorensen=0.6,
            orientation_error_deg=10.0,
        )


def test_main_writes_grid_and_holdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The script writes the grid and frozen holdout using its runner hooks."""
    import ws4.fire.calibration as calibration_module
    import ws4.fire.comparison as comparison_module

    points = (CalibrationParameters(1.0, 1.0), CalibrationParameters(0.5, 0.5))

    def fake_run(fire: object, **kwargs: object) -> FakeCase:
        return FakeCase(str(kwargs["scenario"]))

    monkeypatch.setattr(calibration_module, "parameter_grid", lambda: points)
    monkeypatch.setattr(comparison_module, "run_observed_case", fake_run)
    monkeypatch.setattr(comparison_module, "run_dogrib_case", fake_run)
    output = tmp_path / "grid.csv"
    summary = tmp_path / "grid.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["benchmark_hay_river_calibration.py", "--output", str(output), "--summary", str(summary)],
    )

    module.main()

    frame = pd.read_csv(output)
    assert list(frame["fire"]) == ["hay_river", "hay_river", "dogrib", "dogrib"]
    assert frame["score"].notna().all()
    assert summary.is_file()
